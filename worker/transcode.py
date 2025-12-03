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
import secrets
from pathlib import Path
import re
from datetime import datetime, timezone
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

# Paths that should never be allowed as media directories (shared constant)
FORBIDDEN_SYSTEM_PATHS = ['/', '/etc', '/root', '/sys', '/proc', '/dev', '/bin', '/sbin', '/usr', '/var', '/tmp']

# Configurable allowed media paths for validation (comma-separated)
# Parse and validate each path to ensure it's absolute and doesn't contain path traversal attempts
def _parse_media_paths():
    """Parse and validate MEDIA_PATHS from environment variable."""
    paths = []
    raw_paths = os.environ.get('MEDIA_PATHS', '/media').split(',')
    
    for path in raw_paths:
        path = path.strip()
        if not path:
            continue
        # Check if path is absolute (reject relative paths)
        if not os.path.isabs(path):
            print(f"⚠️ WARNING: Ignoring relative path in MEDIA_PATHS: {path}")
            continue
        # Normalize the path to resolve any .. or . components
        normalized = os.path.normpath(path)
        # Reject paths that normalize to sensitive system directories
        # This catches paths like '/media/../../etc' which normalize to '/etc'
        if normalized in FORBIDDEN_SYSTEM_PATHS:
            print(f"⚠️ WARNING: Ignoring forbidden system path in MEDIA_PATHS: {path} -> {normalized}")
            continue
        paths.append(normalized)
    return paths if paths else ['/media']  # Fallback to default if no valid paths

MEDIA_PATHS = _parse_media_paths()

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

# Generate a unique session token for this worker instance
# This ensures that only one worker with this hostname can be active at a time
SESSION_TOKEN = None

# --- USER CONFIGURATION SECTION ---
# Read DB config from environment variables, with fallbacks for local testing
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "192.168.10.120"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "user": os.environ.get("DB_USER", "transcode"),
    "password": os.environ.get("DB_PASSWORD"),
    "dbname": os.environ.get("DB_NAME", "librarrarian")
}

# ===========================
# Database Layer
# ===========================

class DatabaseHandler:
    def __init__(self, conn_params):
        self.conn_params = conn_params

    def _get_conn(self):
        return psycopg2.connect(**self.conn_params)

    def update_heartbeat(self, status, current_file=None, progress=None, fps=None, version_mismatch=False, total_duration=None, job_start_time=None):
        """
        Updates the worker's status in the central database.
        Note: session_token is NOT included in this UPDATE because it's set during registration
        and should persist unchanged across heartbeat updates. The ON CONFLICT DO UPDATE clause
        only modifies the explicitly listed columns, leaving session_token untouched.
        """
        sql = """
        INSERT INTO nodes (hostname, last_heartbeat, status, version, current_file, progress, fps, version_mismatch, total_duration, job_start_time)
        VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (hostname) DO UPDATE SET
            last_heartbeat = EXCLUDED.last_heartbeat,
            status = EXCLUDED.status,
            version = EXCLUDED.version,
            current_file = EXCLUDED.current_file,
            progress = EXCLUDED.progress,
            fps = EXCLUDED.fps,
            version_mismatch = EXCLUDED.version_mismatch,
            total_duration = EXCLUDED.total_duration,
            job_start_time = EXCLUDED.job_start_time;
        """
        conn = self._get_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (HOSTNAME, status, VERSION, current_file, progress, fps, version_mismatch, total_duration, job_start_time))
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
            "hw_pre_args": ["-vaapi_device", device_path, "-hwaccel", "vaapi", "-hwaccel_output_format", "vaapi"], 
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

def generate_session_token():
    """Generates a unique session token for this worker instance."""
    return secrets.token_hex(32)  # 64 character hex string

def register_with_dashboard():
    """
    Registers this worker with the dashboard using a unique session token.
    Returns True if registration succeeds, False otherwise.
    """
    global SESSION_TOKEN
    
    if not SESSION_TOKEN:
        SESSION_TOKEN = generate_session_token()
    
    try:
        headers = {'X-API-Key': API_KEY} if API_KEY else {}
        payload = {
            "hostname": HOSTNAME,
            "session_token": SESSION_TOKEN,
            "version": VERSION
        }
        
        print(f"[{datetime.now()}] Registering with dashboard as '{HOSTNAME}'...")
        response = requests.post(
            f"{DASHBOARD_URL}/api/register_worker",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 409:
            # Registration rejected - another worker with this hostname is active
            error_data = response.json()
            print("="*70)
            print("❌ REGISTRATION REJECTED")
            print(f"   {error_data.get('error', 'Unknown error')}")
            print(f"   {error_data.get('message', '')}")
            print("="*70)
            return False
        
        response.raise_for_status()
        result = response.json()
        
        if result.get('success'):
            print(f"[{datetime.now()}] ✅ Successfully registered with dashboard")
            return True
        else:
            print(f"[{datetime.now()}] ❌ Registration failed: {result}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] ❌ Registration Error: Could not connect to dashboard. {e}")
        print("    Ensure the dashboard is running and accessible from this machine.")
        if 'localhost' in DASHBOARD_URL:
            print("    If running the worker on a different machine, set the DASHBOARD_URL environment variable.")
            print("    Example: DASHBOARD_URL=http://<dashboard_ip>:5000")
        return False

def get_dashboard_settings():
    """Fetches all worker settings from the dashboard's API."""
    try:
        headers = {'X-API-Key': API_KEY} if API_KEY else {}
        params = {"hostname": HOSTNAME, "session_token": SESSION_TOKEN} if SESSION_TOKEN else {}
        response = requests.get(f"{DASHBOARD_URL}/api/settings", headers=headers, params=params, timeout=10)
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
    if not SESSION_TOKEN:
        print(f"[{datetime.now()}] ERROR: Cannot request job - worker is not registered")
        return None
    
    try:
        print(f"[{datetime.now()}] Requesting a new job...")
        headers = {'X-API-Key': API_KEY} if API_KEY else {}
        payload = {"hostname": HOSTNAME, "session_token": SESSION_TOKEN}
        response = requests.post(f"{DASHBOARD_URL}/api/request_job", json=payload, headers=headers, timeout=10)
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
    if not SESSION_TOKEN:
        print(f"[{datetime.now()}] ERROR: Cannot update job status - worker is not registered")
        return
    
    payload = {"status": status, "hostname": HOSTNAME, "session_token": SESSION_TOKEN}
    if details:
        payload.update(details)
    
    try:
        headers = {'X-API-Key': API_KEY} if API_KEY else {}
        response = requests.post(f"{DASHBOARD_URL}/api/update_job/{job_id}", json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"[{datetime.now()}] Successfully updated job {job_id} to status '{status}'.")
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] API Error: Could not update job {job_id}. {e}")

def validate_filepath(filepath):
    """
    Validates that a filepath doesn't contain path traversal attempts.
    Prevents security vulnerabilities from malicious paths like '../../../etc/passwd'.
    Returns True if the path is safe, False otherwise.
    """
    try:
        # Resolve the absolute path and normalize it
        resolved_path = os.path.realpath(os.path.abspath(filepath))
        
        # Use configurable allowed base directories from environment
        # Normalize all base paths once to avoid redundant computation
        allowed_bases_raw = list(MEDIA_PATHS) + [os.path.abspath('.')]
        allowed_bases_normalized = []
        for base in allowed_bases_raw:
            try:
                base_real = os.path.realpath(os.path.abspath(base))
                allowed_bases_normalized.append(base_real)
            except (ValueError, TypeError):
                continue
        
        # Check if the resolved path is within any allowed base directory
        # Using os.path.commonpath for robust containment checking
        is_allowed = False
        for base_real in allowed_bases_normalized:
            try:
                # Use os.path.commonpath to check if resolved_path is under base_real
                # This is the most secure way to check path containment
                common = os.path.commonpath([base_real, resolved_path])
                # If the common path equals the base, then resolved_path is under base
                if common == base_real:
                    is_allowed = True
                    break
            except ValueError:
                # commonpath raises ValueError if paths are on different drives (Windows)
                # or have no common path - in either case, not allowed
                continue
        
        if not is_allowed:
            print(f"⚠️ WARNING: Path outside allowed directories detected and blocked: {filepath}")
            print(f"   Allowed directories: {', '.join(allowed_bases_raw)}")
            return False
            
        # Additional check: block access to sensitive system directories
        # BUT: only block if the path would escape from under our allowed directories
        # Since we've already confirmed the path is under an allowed base, we need to check
        # if that allowed base itself is trying to access a forbidden directory
        # OR if the path tries to traverse to a forbidden directory
        for sensitive in FORBIDDEN_SYSTEM_PATHS:
            try:
                # Skip root (/) since all absolute paths are under root, making this check overly restrictive
                if sensitive == '/':
                    continue
                    
                sensitive_real = os.path.realpath(sensitive)
                # Check if resolved_path is under or equal to sensitive directory
                try:
                    common = os.path.commonpath([sensitive_real, resolved_path])
                    if common == sensitive_real:
                        # The path is under a sensitive directory
                        # But we should only block if none of the allowed bases
                        # are also under this sensitive directory (meaning the user
                        # explicitly configured access to that area)
                        allowed_under_sensitive = False
                        for base_real in allowed_bases_normalized:
                            try:
                                base_common = os.path.commonpath([sensitive_real, base_real])
                                if base_common == sensitive_real:
                                    # The allowed base is under the sensitive directory
                                    # so this is explicitly allowed by config
                                    allowed_under_sensitive = True
                                    break
                            except ValueError:
                                continue
                        
                        if not allowed_under_sensitive:
                            print(f"⚠️ WARNING: Access to sensitive directory blocked: {filepath}")
                            return False
                except ValueError:
                    # Different drives or no common path - not a concern
                    continue
            except (OSError, ValueError):
                # If we can't resolve the sensitive path, skip this check
                continue
            
        return True
    except Exception as e:
        print(f"⚠️ WARNING: Error validating filepath {filepath}: {e}")
        return False

def translate_path_for_worker(filepath, settings):
    """
    Translates a container-centric path from the dashboard to a path the worker can use.
    This is crucial for non-Docker workers or complex mount setups.
    """
    # First validate the filepath for security
    if not validate_filepath(filepath):
        print(f"❌ ERROR: Refusing to process potentially malicious filepath: {filepath}")
        return None
    
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
    # Translate the dashboard path to the worker's local path
    local_filepath = translate_path_for_worker(filepath, settings)
    if local_filepath is None:
        return False, {"reason": "Invalid or malicious filepath detected", "log": f"Filepath validation failed for: {filepath}"}
    
    print(f"[{datetime.now()}] Starting transcode for: {local_filepath}")
    job_start_time = datetime.now(timezone.utc)
    db.update_heartbeat('encoding', current_file=os.path.basename(local_filepath), progress=0, fps=0, job_start_time=job_start_time)

    # --- Get settings from the dashboard ---
    hw_mode = settings.get('hardware_acceleration', 'auto')
    hw_config = detect_hardware_settings(hw_mode)
    
    # Determine which CQ value to use based on video width
    try:
        ffprobe_cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width", "-of", "csv=s=x:p=0", local_filepath]
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
    original_path = Path(local_filepath)
    temp_output_path = original_path.parent / f"tmp_{original_path.name}"
    final_output_path = original_path.with_suffix('.mkv') # Always output to MKV
    
    # --- Get original file size before transcoding ---
    # We do this early because the file could be moved/deleted by external processes
    # (Plex, Sonarr, etc.) after transcoding completes
    try:
        original_size = os.path.getsize(original_path)
    except FileNotFoundError:
        print(f"[{datetime.now()}] FAILED: Original file not found before transcode: {original_path}")
        return False, {"reason": "Original file not found", "log": f"File disappeared before transcoding could start: {original_path}"}

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
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, universal_newlines=True, errors='replace')
    
    total_duration_seconds = 0
    log_buffer = []

    for line in process.stdout:
        log_buffer.append(line)
        if "Duration:" in line:
            match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
            if match:
                h, m, s, ms = map(int, match.groups())
                total_duration_seconds = h * 3600 + m * 60 + s + ms / 100.0
                # Send total duration to dashboard once we know it
                db.update_heartbeat('encoding', current_file=os.path.basename(local_filepath), progress=0, fps=0, total_duration=total_duration_seconds, job_start_time=job_start_time)

        if "frame=" in line and total_duration_seconds > 0:
            time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
            fps_match = re.search(r'fps=\s*([\d\.]+)', line)
            if time_match:
                h, m, s, ms = map(int, time_match.groups())
                current_seconds = h * 3600 + m * 60 + s + ms / 100.0
                progress = round((current_seconds / total_duration_seconds) * 100)
                fps = float(fps_match.group(1)) if fps_match else 0
                db.update_heartbeat('encoding', current_file=os.path.basename(local_filepath), progress=progress, fps=fps, total_duration=total_duration_seconds, job_start_time=job_start_time)

    process.wait()

    # --- Process Results ---
    if process.returncode == 0:
        print(f"[{datetime.now()}] Finished transcode for: {local_filepath}")
        
        # Check if temp file was created successfully
        if not os.path.exists(temp_output_path):
            print(f"[{datetime.now()}] FAILED: Temporary output file not created: {temp_output_path}")
            return False, {"reason": "FFmpeg did not create output file", "log": "".join(log_buffer)}
        
        new_size = os.path.getsize(temp_output_path)

        # Handle file replacement
        # Check if original file still exists (it might have been moved/deleted by external process)
        original_exists = os.path.exists(original_path)
        
        if not original_exists:
            print(f"⚠️ WARNING: Original file disappeared during transcode: {original_path}")
            print(f"  -> This may have been moved/deleted by Plex, Sonarr, or another process")
            print(f"  -> Skipping original file cleanup, proceeding with temp file rename")
        elif settings.get('keep_original') == 'true':
            backup_dir_str = settings.get('backup_directory', '')
            if backup_dir_str:
                try:
                    backup_path = Path(backup_dir_str) / original_path.name
                    print(f"  -> Moving original to backup: {backup_path}")
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(original_path, backup_path)
                except FileNotFoundError:
                    print(f"[{datetime.now()}]   -> Original file disappeared before backup, skipping")
            else:
                print("  -> Keeping original file (no backup directory specified).")
        else:
            try:
                print(f"  -> Deleting original file: {original_path}")
                os.remove(original_path)
            except FileNotFoundError:
                print(f"[{datetime.now()}]   -> Original file already deleted, skipping")
        
        print(f"  -> Renaming temporary file to final output: {final_output_path}")
        os.rename(temp_output_path, final_output_path)

        return True, {"original_size": original_size, "new_size": new_size}
    else:
        print(f"[{datetime.now()}] FAILED transcode for: {local_filepath}. FFmpeg exited with code {process.returncode}")
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
    if local_filepath is None:
        return False, {"reason": "Invalid or malicious filepath detected", "log": f"Filepath validation failed for: {filepath}"}
    
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

def rename_file(filepath, db, settings, metadata):
    """
    Renames a file based on metadata from Sonarr/Radarr.
    """
    # Translate the dashboard path to the worker's local path
    local_filepath = translate_path_for_worker(filepath, settings)
    if local_filepath is None:
        return False, {"reason": "Invalid or malicious filepath detected", "log": f"Filepath validation failed for: {filepath}"}
    
    print(f"[{datetime.now()}] Starting rename for: {local_filepath}")
    db.update_heartbeat('renaming', current_file=os.path.basename(local_filepath))

    if not metadata or metadata.get('source') != 'sonarr':
        return False, {"reason": "Invalid or missing metadata for rename job."}

    try:
        series_title = metadata.get('seriesTitle', 'Unknown Series')
        season_number = metadata.get('seasonNumber')
        episode_number = metadata.get('episodeNumber')
        episode_title = metadata.get('episodeTitle', 'Unknown Episode')
        quality = metadata.get('quality', 'Unknown Quality')

        # Sanitize components for filesystem
        series_title = re.sub(r'[<>:"/\\|?*]', '', series_title)
        episode_title = re.sub(r'[<>:"/\\|?*]', '', episode_title)

        # Construct the new filename, e.g., "Series Title - S01E01 - Episode Title [Quality].mkv"
        new_filename = f"{series_title} - S{season_number:02d}E{episode_number:02d} - {episode_title} [{quality}]{Path(local_filepath).suffix}"
        new_filepath = Path(local_filepath).parent / new_filename

        print(f"  -> Renaming to: {new_filepath}")
        os.rename(local_filepath, new_filepath)
        return True, {"new_filename": str(new_filepath)}
    except Exception as e:
        return False, {"reason": "File rename operation failed on worker.", "log": str(e)}

def main_loop(db):
    """The main worker loop."""
    print(f"[{datetime.now()}] Worker '{HOSTNAME}' starting up. Version: {VERSION}")
    
    # Register with the dashboard to get a session token and ensure uniqueness
    if not register_with_dashboard():
        print(f"[{datetime.now()}] ❌ Failed to register with dashboard. Exiting.")
        sys.exit(1)
    
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
            settings, _ = get_dashboard_settings() # Refresh settings before each job
            if job.get('job_type') == 'cleanup':
                success, details = cleanup_file(job['filepath'], db, settings)
            elif job.get('job_type') == 'Rename Job':
                success, details = rename_file(job['filepath'], db, settings, job.get('metadata'))
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