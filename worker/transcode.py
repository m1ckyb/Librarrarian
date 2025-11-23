#!/usr/bin/env python3
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
DASHBOARD_URL = os.environ.get('DASHBOARD_URL', 'http://dashboard:5000')
DB_HOST = os.environ.get("DB_HOST", "192.168.10.120")
VERSION = "1.0-beta"
HOSTNAME = socket.gethostname()
STOP_EVENT = threading.Event()

# --- USER CONFIGURATION SECTION ---
# Read DB config from environment variables, with fallbacks for local testing
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "192.168.10.120"),
    "user": os.environ.get("POSTGRES_USER", "transcode"),
    "password": os.environ.get("POSTGRES_PASSWORD", "password"),
    "dbname": os.environ.get("POSTGRES_DB", "codecshift")
}

# ===========================
# Database Layer
# ===========================

class DatabaseHandler:
    def __init__(self, conn_params):
        self.conn_params = conn_params

    def get_conn(self):
        return psycopg2.connect(**self.conn_params)

    def update_heartbeat(self, status, current_file=None, progress=None, fps=None):
        """Updates the worker's status in the central database."""
        sql = """
        INSERT INTO nodes (hostname, last_heartbeat, status, version, current_file, progress, fps)
        VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s, %s)
        ON CONFLICT (hostname) DO UPDATE SET
            last_heartbeat = EXCLUDED.last_heartbeat,
            status = EXCLUDED.status,
            version = EXCLUDED.version,
            current_file = EXCLUDED.current_file,
            progress = EXCLUDED.progress,
            fps = EXCLUDED.fps;
        """
        conn = self.get_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (HOSTNAME, datetime.now(), status, VERSION, current_file, progress, fps))
                conn.commit()
            except Exception as e:
                print(f"[{datetime.now()}] Heartbeat Error: Could not update status. {e}")
            finally:
                conn.close()

    def get_node_command(self, hostname):
        """Fetches the status for a specific node, which can act as a command."""
        conn = self.get_conn()
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
        conn = self.get_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM active_nodes WHERE hostname = %s", (HOSTNAME,))
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

def request_job_from_dashboard():
    """Requests a new job from the dashboard's API."""
    try:
        print(f"[{datetime.now()}] Requesting a new job...")
        response = requests.post(f"{DASHBOARD_URL}/api/request_job", json={"hostname": HOSTNAME}, timeout=10)
        response.raise_for_status()
        job_data = response.json()
        if job_data and 'job_id' in job_data:
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
        response = requests.post(f"{DASHBOARD_URL}/api/update_job/{job_id}", json=payload, timeout=10)
        response.raise_for_status()
        print(f"[{datetime.now()}] Successfully updated job {job_id} to status '{status}'.")
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] API Error: Could not update job {job_id}. {e}")

def process_file(filepath, db):
    """
    Placeholder for the actual ffmpeg transcoding logic.
    Returns a tuple: (success, details_dict).
    """
    print(f"[{datetime.now()}] Starting transcode for: {filepath}")
    db.update_heartbeat('encoding', current_file=os.path.basename(filepath), progress=0, fps=0)
    
    # --- Placeholder for your complex ffmpeg logic ---
    # This is where you would build and run the ffmpeg command,
    # parse its output for progress, and handle hardware acceleration.
    
    try:
        # Simulate a transcode process
        original_size = os.path.getsize(filepath)
        time.sleep(15) # Simulate work
        
        # In a real implementation, you would get the new size from the output file.
        new_size = original_size * 0.4 

        # Simulate success
        print(f"[{datetime.now()}] Finished transcode for: {filepath}")
        return True, {"original_size": original_size, "new_size": new_size}

    except Exception as e:
        # Simulate failure
        print(f"[{datetime.now()}] FAILED transcode for: {filepath}. Reason: {e}")
        return False, {"reason": "Placeholder processing error", "log": str(e)}

def cleanup_file(filepath, db):
    """
    Deletes a single stale file identified by the dashboard.
    Returns a tuple: (success, details_dict).
    """
    print(f"[{datetime.now()}] Starting cleanup for: {filepath}")
    db.update_heartbeat('cleaning', current_file=os.path.basename(filepath))
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"[{datetime.now()}] Successfully deleted stale file: {filepath}")
            return True, {}
        else:
            print(f"[{datetime.now()}] Stale file not found (already deleted?): {filepath}")
            return True, {"reason": "File not found on worker"} # Still success, as the file is gone
    except Exception as e:
        print(f"[{datetime.now()}] FAILED cleanup for: {filepath}. Reason: {e}")
        return False, {"reason": "File deletion error on worker", "log": str(e)}

def main_loop(db):
    """The main worker loop."""
    print(f"[{datetime.now()}] Worker '{HOSTNAME}' starting up. Version: {VERSION}")
    db.update_heartbeat('booting')
    time.sleep(2) # Stagger startup

    while not STOP_EVENT.is_set():
        db.update_heartbeat('idle')
        command = db.get_node_command(HOSTNAME)

        if command == 'quit':
            print(f"[{datetime.now()}] Quit command received. Shutting down.")
            STOP_EVENT.set()
            db.update_heartbeat('offline')
            break

        if command == 'start':
            job = request_job_from_dashboard()

            if job:
                # Check the job type and call the appropriate function
                if job.get('job_type') == 'cleanup':
                    success, details = cleanup_file(job['filepath'], db)
                else: # Default to 'transcode'
                    success, details = process_file(job['filepath'], db)

                # Report the result back to the dashboard
                if success:
                    update_job_status(job['job_id'], 'completed', details)
                else:
                    update_job_status(job['job_id'], 'failed', details)
                
                # Immediately check for another job without waiting
                continue 

            else:
                # No jobs were available, wait before asking again
                print(f"[{datetime.now()}] No jobs. Waiting for 60 seconds...")
                db.update_heartbeat('idle')
                time.sleep(60)
        
        else: # idle, stop, pause, etc.
            print(f"[{datetime.now()}] In '{command}' state. Standing by...")
            db.update_heartbeat(command)
            time.sleep(30) # Check for new commands every 30 seconds

# ===========================
# Main Execution
# ===========================

def main():
    # Connect to DB using centralized config
    db = DatabaseHandler(DB_CONFIG)
    if not db.get_conn():
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
        # db.clear_node() # Optional: decide if node should be cleared on exit
        print("Node offline.")

if __name__ == "__main__":
    main()