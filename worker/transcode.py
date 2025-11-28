#!/usr/bin/env python3
import os
import sys
import time
import shutil
import argparse
import subprocess
import socket
import threading
import json
from pathlib import Path
import re
from datetime import datetime
import requests

# Check for Postgres Driver
try:
    import psycopg2
except ImportError:
    print("❌ Error: Missing PostgreSQL driver.")
    print("   Please run: pip3 install psycopg2-binary")
    sys.exit(1)

# ===========================
# Global Settings
# ===========================
DASHBOARD_URL = os.environ.get('DASHBOARD_URL', 'http://localhost:5000')
DB_HOST = os.environ.get("DB_HOST", "192.168.10.120")

def get_worker_version():
    """Reads the version from the VERSION.txt file."""
    try:
        # This works in Docker where VERSION.txt is in the workdir.
        return open('VERSION.txt', 'r').read().strip()
    except FileNotFoundError:
        # Fallback for local development where the script is in a subdirectory.
        try:
            return open(os.path.join(os.path.dirname(__file__), '..', 'VERSION.txt'), 'r').read().strip()
        except FileNotFoundError:
            return "standalone"
VERSION = get_worker_version()
HOSTNAME = socket.gethostname()
STOP_EVENT = threading.Event()
API_KEY = os.environ.get('API_KEY')

# --- USER CONFIGURATION SECTION ---
# Read DB config from environment variables, with fallbacks for local testing
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "192.168.10.120"),
    "user": os.environ.get("DB_USER", "transcode"),
    "password": os.environ.get("POSTGRES_PASSWORD", "password"),
    "dbname": os.environ.get("POSTGRES_DB", "transcode_cluster")
}

# ===========================
# Database Layer
# ===========================

class DatabaseHandler:
    def __init__(self, conn_params):
        self.conn_params = conn_params

    def _get_conn(self):
        return psycopg2.connect(**self.conn_params)

    def update_heartbeat(self, status, current_file=None, progress=None, fps=None, version_mismatch=False):
        """Updates the worker's status in the central database."""
        sql = """
        INSERT INTO nodes (hostname, last_heartbeat, status, version, current_file, progress, fps, version_mismatch)
        VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s)
        ON CONFLICT (hostname) DO UPDATE SET
            last_heartbeat = EXCLUDED.last_heartbeat,
            status = EXCLUDED.status,
            version = EXCLUDED.version,
            current_file = EXCLUDED.current_file,
            progress = EXCLUDED.progress,
            fps = EXCLUDED.fps,
            version_mismatch = EXCLUDED.version_mismatch;
        """
        conn = self._get_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (HOSTNAME, status, VERSION, current_file, progress, fps, version_mismatch))
                conn.commit()
            except Exception as e:
                print(f"[{datetime.now()}] Heartbeat Error: Could not update status. {e}")
            finally:
                conn.close()

    def get_node_command(self, hostname):
        """Fetches the status for a specific node, which can act as a command."""
        conn = self._get_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT command FROM nodes WHERE hostname = %s", (hostname,))
                    result = cur.fetchone()
                    return result[0] if result else 'idle'
            finally:
                conn.close()
        return 'idle'

    def clear_node(self):
        conn = self._get_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM nodes WHERE hostname = %s", (HOSTNAME,))
                conn.commit()
            finally:
                conn.close()

# ===========================
# Hardware Configuration
# ===========================

def get_hw_config(mode, device_path="/dev/dri/renderD128"):
    if mode == "nvidia":
        return {
            "type": "nvidia", "codec": "hevc_nvenc", "hw_pre_args": ["-hwaccel", "cuda"], 
            "preset": "p3", "cq_flag": "-cq", "extra": ["-rc", "vbr"]
        }
    elif mode == "qsv":
        return {
            "type": "intel", "codec": "hevc_qsv", 
            "hw_pre_args": ["-init_hw_device", f"qsv=hw,child_device={device_path}", "-hwaccel", "qsv", "-hwaccel_output_format", "qsv"], 
            "preset": "medium", "cq_flag": "-global_quality", "extra": [] 
        }
    elif mode == "vaapi":
        return {
            "type": "intel", "codec": "hevc_vaapi", 
            "hw_pre_args": ["-init_hw_device", f"vaapi=va:{device_path}", "-hwaccel", "vaapi", "-hwaccel_output_format", "vaapi", "-hwaccel_device", "va"], 
            "preset": None, "cq_flag": "-global_quality", "extra": []
        }
    else: 
        return {"type": "cpu", "codec": "libx265", "hw_pre_args": [], "preset": "medium", "cq_flag": "-crf", "extra": []}

def detect_hardware_settings(accel_mode):
    if accel_mode == "nvidia": return get_hw_config("nvidia")
    if accel_mode == "qsv": return get_hw_config("qsv")
    if accel_mode == "vaapi": return get_hw_config("vaapi")
    if accel_mode == "cpu": return get_hw_config("cpu")

    print("🔍 Probing Hardware...", end=" ", flush=True)

    # --- Universal FFmpeg Capability Check ---
    try:
        # Run these once to avoid multiple subprocess calls
        hw_out = subprocess.check_output(["ffmpeg", "-hide_banner", "-hwaccels"], text=True, stderr=subprocess.STDOUT)
        enc_out = subprocess.check_output(["ffmpeg", "-hide_banner", "-encoders"], text=True, stderr=subprocess.STDOUT)
    except (FileNotFoundError, subprocess.CalledProcessError):
        # If ffmpeg isn't found or fails, we can only use CPU
        print("⚠️ FFmpeg not found or failed, falling back to CPU.")
        return get_hw_config("cpu")

    # --- Check 1: NVIDIA (Priority) ---
    # This is the most reliable check for Linux, Docker, and WSL with NVIDIA drivers.
    # It checks if ffmpeg was compiled with CUDA support and can see the nvenc encoder.
    # We also check for `nvidia-smi` to confirm that hardware is actually present.
    if "cuda" in hw_out and "hevc_nvenc" in enc_out:
        try:
            # The presence of nvidia-smi is a strong indicator of an actual NVIDIA GPU.
            subprocess.check_output(["which", "nvidia-smi"], stderr=subprocess.STDOUT)
            print("✅ Found NVIDIA")
            return get_hw_config("nvidia")
        except (subprocess.CalledProcessError, FileNotFoundError):
            # nvidia-smi not found, so it's not a real NVIDIA system.
            pass

    # --- Check 2: VAAPI (Intel/AMD on Linux) ---
    if "vaapi" in hw_out and "hevc_vaapi" in enc_out and sys.platform.startswith('linux'):
        print("✅ Found VAAPI")
        return get_hw_config("vaapi")
        
    return get_hw_config("cpu")

# ===========================
# Worker Logic
# ===========================

def get_dashboard_settings():
    """Fetches all worker settings from the dashboard's API."""
    try:
        headers = {'X-API-Key': API_KEY} if API_KEY else {}
        response = requests.get(f"{DASHBOARD_URL}/api/settings", headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        settings_data = data.get('settings', {})
        dashboard_version = data.get('dashboard_version')
        # Flatten the settings for easier access
        return {key: value['setting_value'] for key, value in settings_data.items()}, dashboard_version
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] API Error: Could not fetch settings from {DASHBOARD_URL}. {e}")
        print("    Ensure the dashboard is running and accessible from this machine.")
        if 'localhost' in DASHBOARD_URL:
            print("    If running the worker on a different machine, set the DASHBOARD_URL environment variable. Example: DASHBOARD_URL=http://<dashboard_ip>:5000 ./transcode.py")
        return {}, None

def request_job_from_dashboard():
    """Requests a new job from the dashboard's API."""
    try:
        print(f"[{datetime.now()}] Requesting a new job...")
        headers = {'X-API-Key': API_KEY} if API_KEY else {}
        response = requests.post(f"{DASHBOARD_URL}/api/request_job", json={"hostname": HOSTNAME}, headers=headers, timeout=10)
        response.raise_for_status()
        job_data = response.json()
        if job_data and job_data.get('job_id'):
            print(f"[{datetime.now()}] Received job {job_data['job_id']} for file: {job_data['filepath']}")
            return job_data
        else:
            print(f"[{datetime.now()}] No pending jobs available.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] API Error: Could not request job. {e}")
        return None

def update_job_status(job_id, status, details=None):
    """Updates the job's status via the dashboard's API."""
    payload = {"status": status}
    if details:
        payload.update(details)
    
    try:
        headers = {'X-API-Key': API_KEY} if API_KEY else {}
        response = requests.post(f"{DASHBOARD_URL}/api/update_job/{job_id}", json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"[{datetime.now()}] Successfully updated job {job_id} to status '{status}'.")
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] API Error: Could not update job {job_id}. {e}")

def translate_path_for_worker(filepath, settings):
    """
    Translates a container-centric path from the dashboard to a path the worker can use.
    This is crucial for non-Docker workers or complex mount setups.
    """
    path_from = settings.get('plex_path_from')
    path_to = settings.get('plex_path_to')

    # If mappings are defined and the incoming path starts with the container path (`path_to`),
    # replace it with the Plex path (`path_from`). This gives us the "real" network path.
    if path_from and path_to and filepath.startswith(path_to):
        # This is a simple replacement for now. A more robust solution might be needed
        # if the worker's root path isn't the project directory.
        return filepath.replace(path_to, path_from, 1)
    return filepath
def process_file(filepath, db, settings):
    """Handles the full transcoding process for a given file using ffmpeg."""
    print(f"[{datetime.now()}] Starting transcode for: {filepath}")
    db.update_heartbeat('encoding', current_file=os.path.basename(filepath), progress=0, fps=0)

    # --- Get settings from the dashboard ---
    hw_mode = settings.get('hardware_acceleration', 'auto')
    hw_config = detect_hardware_settings(hw_mode)
    
    # Determine which CQ value to use based on video width
    try:
        ffprobe_cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width", "-of", "csv=s=x:p=0", filepath]
        width_str = subprocess.check_output(ffprobe_cmd, text=True).strip()
        video_width = int(width_str)
        cq_width_threshold = int(settings.get('cq_width_threshold', '1900'))
        
        if video_width >= cq_width_threshold:
            cq_value = settings.get(f"{hw_config['type']}_cq_hd", '28')
        else:
            cq_value = settings.get(f"{hw_config['type']}_cq_sd", '24')
    except Exception as e:
        print(f"⚠️ Could not determine video width, falling back to SD quality. Error: {e}")
        cq_value = settings.get(f"{hw_config['type']}_cq_sd", '24')

    # --- Prepare file paths ---
    original_path = Path(filepath)
    temp_output_path = original_path.parent / f"tmp_{original_path.name}"
    final_output_path = original_path.with_suffix('.mkv') # Always output to MKV

    # --- Build FFmpeg Command ---
    ffmpeg_cmd = ["ffmpeg", "-y", "-hide_banner"]
    ffmpeg_cmd.extend(hw_config["hw_pre_args"])
    ffmpeg_cmd.extend(["-i", str(original_path)])
    ffmpeg_cmd.extend([
        "-map", "0", "-c", "copy", "-c:v:0", hw_config["codec"],
        hw_config["cq_flag"], str(cq_value)
    ])
    if hw_config["preset"]:
        ffmpeg_cmd.extend(["-preset", hw_config["preset"]])
    ffmpeg_cmd.extend(hw_config["extra"])
    ffmpeg_cmd.append(str(temp_output_path))

    print(f"🔩 FFmpeg command: {' '.join(ffmpeg_cmd)}")

    # --- Execute FFmpeg and Capture Output ---
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True)
    
    total_duration_seconds = 0
    log_buffer = []

    for line in process.stdout:
        log_buffer.append(line)
        if "Duration:" in line:
            match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
            if match:
                h, m, s, ms = map(int, match.groups())
                total_duration_seconds = h * 3600 + m * 60 + s + ms / 100.0

        if "frame=" in line and total_duration_seconds > 0:
            time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
            fps_match = re.search(r'fps=\s*([\d\.]+)', line)
            if time_match:
                h, m, s, ms = map(int, time_match.groups())
                current_seconds = h * 3600 + m * 60 + s + ms / 100.0
                progress = round((current_seconds / total_duration_seconds) * 100)
                fps = float(fps_match.group(1)) if fps_match else 0
                db.update_heartbeat('encoding', current_file=os.path.basename(filepath), progress=progress, fps=fps)

    process.wait()

    # --- Process Results ---
    if process.returncode == 0:
        print(f"[{datetime.now()}] Finished transcode for: {filepath}")
        original_size = os.path.getsize(filepath)
        new_size = os.path.getsize(temp_output_path)

        # Handle file replacement
        if settings.get('keep_original') == 'true':
            backup_dir_str = settings.get('backup_directory', '')
            if backup_dir_str:
                backup_path = Path(backup_dir_str) / original_path.name
                print(f"  -> Moving original to backup: {backup_path}")
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(original_path, backup_path)
            else:
                print("  -> Keeping original file (no backup directory specified).")
        else:
            print(f"  -> Deleting original file: {original_path}")
            os.remove(original_path)
        
        print(f"  -> Renaming temporary file to final output: {final_output_path}")
        os.rename(temp_output_path, final_output_path)

        return True, {"original_size": original_size, "new_size": new_size}
    else:
        print(f"[{datetime.now()}] FAILED transcode for: {filepath}. FFmpeg exited with code {process.returncode}")
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
        return False, {"reason": f"FFmpeg failed with code {process.returncode}", "log": "".join(log_buffer)}

def cleanup_file(filepath, db, settings):
    """
    Deletes a single stale file identified by the dashboard.
    Returns a tuple: (success, details_dict).
    """
    print(f"[{datetime.now()}] Starting cleanup for: {filepath}")
    local_filepath = translate_path_for_worker(filepath, settings)
    
    db.update_heartbeat('cleaning', current_file=os.path.basename(local_filepath))
    try:
        if os.path.exists(local_filepath):
            os.remove(local_filepath)
            print(f"[{datetime.now()}] Successfully deleted stale file: {local_filepath}")
            return True, {}
        else:
            print(f"[{datetime.now()}] Stale file not found (already deleted?): {local_filepath}")
            return True, {"reason": "File not found on worker"} # Still success, as the file is gone
    except Exception as e:
        print(f"[{datetime.now()}] FAILED cleanup for: {local_filepath}. Reason: {e}")
        return False, {"reason": "File deletion error on worker", "log": str(e)}

def main_loop(db):
    """The main worker loop."""
    print(f"[{datetime.now()}] Worker '{HOSTNAME}' starting up. Version: {VERSION}")
    db.update_heartbeat('booting', version_mismatch=False)
    time.sleep(2) # Stagger startup

    settings, dashboard_version = get_dashboard_settings()
    if not settings:
        print("❌ Could not fetch settings from dashboard on startup. Will retry.")
    
    version_mismatch = False
    if dashboard_version and dashboard_version != VERSION:
        version_mismatch = True
        print("="*60)
        print(f"⚠️  VERSION MISMATCH DETECTED!")
        print(f"   Worker Version:    {VERSION}")
        print(f"   Dashboard Version: {dashboard_version}")
        print("   Please update the worker or dashboard to ensure compatibility.")
        print("="*60)

    # Determine initial state
    autostart = os.environ.get('AUTOSTART', 'false').lower() == 'true'
    current_command = 'running' if autostart else 'idle'
    if autostart:
        print(f"[{datetime.now()}] AUTOSTART is enabled. Worker will start processing jobs immediately.")

    first_loop = True
    while not STOP_EVENT.is_set():
        # On the first loop with autostart, force the command to 'running'
        # to override the default 'idle' state from the database.
        # For subsequent loops, if the command is 'idle', an autostarted worker
        # should treat it as 'running' unless explicitly stopped.
        current_command = db.get_node_command(HOSTNAME)

        if autostart and current_command == 'idle':
            current_command = 'running'

        if current_command == 'quit':
            print(f"[{datetime.now()}] Quit command received. Shutting down.")
            db.update_heartbeat('offline', version_mismatch=version_mismatch)
            break
        
        if current_command in ['idle', 'paused', 'finishing']:
            print(f"[{datetime.now()}] In '{current_command}' state. Standing by...")
            db.update_heartbeat(current_command, version_mismatch=version_mismatch)
            time.sleep(30) # Check for new commands every 30 seconds
            continue

        # If we've reached here, the command is 'running'.
        db.update_heartbeat('running', version_mismatch=version_mismatch)

        job = request_job_from_dashboard()
        if job:
            settings = get_dashboard_settings() # Refresh settings before each job
            if job.get('job_type') == 'cleanup':
                success, details = cleanup_file(job['filepath'], db, settings)
            else: # Default to 'transcode'
                success, details = process_file(job['filepath'], db, settings)
            update_job_status(job['job_id'], 'completed' if success else 'failed', details)
        else:
            # No jobs were available, wait before asking again
            poll_interval = int(settings.get('worker_poll_interval', 30))
            print(f"[{datetime.now()}] No jobs. Waiting for {poll_interval} seconds...")
            time.sleep(poll_interval)
        
        first_loop = False

# ===========================
# Main Execution
# ===========================

def main():
    # Connect to DB using centralized config
    db = DatabaseHandler(DB_CONFIG) # This is now just for heartbeats and commands
    if not db._get_conn():
        sys.exit(1)

    # --- Worker Thread Setup ---
    worker_thread = threading.Thread(target=main_loop, args=(db,))
    worker_thread.daemon = True
    worker_thread.start()
    
    try:
        worker_thread.join() # Wait for the worker to finish
    except KeyboardInterrupt:
        print("\n🛑 Aborted by user. Shutting down gracefully...")
        STOP_EVENT.set()
        worker_thread.join() # Wait for the thread to exit
    finally:
        db.clear_node()
        print("Node offline.")

if __name__ == "__main__":
    main()