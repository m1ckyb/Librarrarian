#!/usr/bin/env python3
import os
import sys
import time
import shutil
import argparse
import subprocess
import socket
import threading
import re
import urllib.request
import json
from pathlib import Path
from collections import namedtuple
from datetime import datetime

# Check for Postgres Driver
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("❌ Error: Missing PostgreSQL driver.")
    print("   Please run: pip3 install psycopg2-binary")
    sys.exit(1)

# ===========================
# Global Settings
# ===========================

def get_project_version():
    """
    Reads the version from the root VERSION.txt file.
    Falls back to 'standalone' if the file is not found (e.g., when run outside the project structure).
    """
    try:
        version_file = Path(__file__).parent.parent / "VERSION.txt"
        return version_file.read_text().strip()
    except FileNotFoundError:
        return "standalone"

VERSION = get_project_version()
HOSTNAME = socket.gethostname()
STOP_EVENT = threading.Event()

# --- USER CONFIGURATION SECTION ---
# Read DB config from environment variables, with fallbacks for local testing
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "192.168.10.120"),
    "user": os.environ.get("DB_USER", "transcode"),
    "password": os.environ.get("DB_PASSWORD", "password"),
    "dbname": os.environ.get("DB_NAME", "transcode_cluster")
}

# ===========================
# Database Layer
# ===========================

class DatabaseHandler:
    def __init__(self, conn_params):
        print(f"DB initialized on {conn_params['host']}")
        self.conn_params = conn_params
        self.init_tables()
        
    def get_conn(self):
        try:
            conn = psycopg2.connect(**self.conn_params)
            conn.autocommit = True
            return conn
        except Exception as e:
            print(f"DB Connect Fail: {e}")
            return None

    def init_tables(self):
        """Creates tables if they don't exist and runs schema migrations for existing tables."""
        conn = self.get_conn()
        if conn:
            with conn.cursor() as cur:
                # Create tables if they don't exist
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS active_nodes (
                        hostname VARCHAR(255) PRIMARY KEY,
                        file TEXT,
                        codec VARCHAR(50),
                        percent INTEGER,
                        speed VARCHAR(50),
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS failed_files (
                        filename TEXT PRIMARY KEY,
                        reason TEXT,
                        reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # --- Schema Migrations ---
                # Add 'version' column to 'active_nodes' if it doesn't exist
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='active_nodes' AND column_name='version') THEN
                            ALTER TABLE active_nodes ADD COLUMN version VARCHAR(50);
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='failed_files' AND column_name='log') THEN
                            ALTER TABLE failed_files ADD COLUMN log TEXT;
                        END IF;
                    END;
                    $$
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS encoded_files (
                        id SERIAL PRIMARY KEY,
                        filename TEXT,
                        hostname VARCHAR(255),
                        codec VARCHAR(50),
                        original_size BIGINT,
                        new_size BIGINT,
                        encoded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS worker_settings (
                        key VARCHAR(50) PRIMARY KEY,
                        value TEXT,
                        description TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # --- Insert default settings if they don't exist ---
                cur.execute("""
                    INSERT INTO worker_settings (key, value, description, updated_at) VALUES
                    ('rescan_delay_minutes', '5', 'Delay in minutes before a worker scans for new files.', NOW()),
                    ('skip_encoded_folder', 'true', 'If true, ignore any directory named "encoded".', NOW()),
                    ('min_length', '1.5', 'Only transcode videos longer than this duration in minutes.', NOW()),
                    ('recursive_scan', 'true', 'Scan subdirectories for video files.', NOW()),
                    ('keep_original', 'false', 'Keep the original file after transcoding.', NOW()),
                    ('backup_directory', '', 'If set, move original files here instead of deleting them.', NOW()),
                    ('allow_hevc', 'false', 'Allow re-encoding of files that are already in HEVC (H.265).', NOW()),
                    ('allow_av1', 'false', 'Allow re-encoding of files that are already in AV1.', NOW()),
                    ('hardware_acceleration', 'auto', 'Force a specific hardware encoder (auto, nvidia, qsv, vaapi, cpu).', NOW()),
                    ('auto_update', 'true', 'Enable the worker to automatically update itself.', NOW()),
                    ('clean_failures', 'false', 'Clean the failed jobs list when the worker starts.', NOW()),
                    ('debug', 'false', 'Enable verbose debug logging for the worker.', NOW()),
                    ('nvenc_cq_hd', '32', 'Constant Quality (CQ) for NVIDIA NVENC on HD+ videos.', NOW()),
                    ('nvenc_cq_sd', '28', 'Constant Quality (CQ) for NVIDIA NVENC on SD videos.', NOW()),
                    ('vaapi_cq_hd', '28', 'Constant Quality (CQ) for Intel/AMD VAAPI on HD+ videos.', NOW()),
                    ('vaapi_cq_sd', '24', 'Constant Quality (CQ) for Intel/AMD VAAPI on SD videos.', NOW()),
                    ('cpu_cq_hd', '28', 'Constant Quality (CRF) for CPU encoding on HD+ videos.', NOW()),
                    ('cpu_cq_sd', '24', 'Constant Quality (CRF) for CPU encoding on SD videos.', NOW()),
                    ('cq_width_threshold', '1900', 'The video width (in pixels) to consider as High Definition (HD).', NOW()),
                    ('extensions', '.mkv,.avi,.mp4,.mov,.wmv,.flv,.m4v,.ts,.mpg,.mpeg', 'Comma-separated list of file extensions to scan.', NOW())
                    ON CONFLICT (key) DO NOTHING;
                """)

                # Add 'status' column to 'active_nodes' if it doesn't exist
                cur.execute("ALTER TABLE active_nodes ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'idle'")

            conn.close()

    def report_success(self, filename, hostname, codec, original_size, new_size):
        """Logs a successfully encoded file to the database."""
        sql = """
        INSERT INTO encoded_files (filename, hostname, codec, original_size, new_size)
        VALUES (%s, %s, %s, %s, %s)
        """
        conn = self.get_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (filename, hostname, codec, original_size, new_size))
            finally:
                conn.close()

    def update_heartbeat(self, filename, codec, percent, speed, version, status='running'):
        sql = """
        INSERT INTO active_nodes (hostname, file, codec, percent, speed, last_updated, version, status)
        VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s)
        ON CONFLICT (hostname) 
        DO UPDATE SET 
            file = EXCLUDED.file,
            codec = EXCLUDED.codec,
            percent = EXCLUDED.percent,
            speed = EXCLUDED.speed,
            status = EXCLUDED.status,
            last_updated = NOW(),
            version = EXCLUDED.version;
        """
        conn = self.get_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (HOSTNAME, filename, codec, percent, speed, version, status))
                # Heartbeats are too frequent to log
            except Exception as e:
                print(f"Heartbeat Failed: {e}")
            finally:
                conn.close()

    def get_cluster_status(self):
        conn = self.get_conn()
        nodes = []
        failures = 0
        if conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT *, EXTRACT(EPOCH FROM (NOW() - last_updated)) as age 
                        FROM active_nodes 
                        WHERE last_updated > NOW() - INTERVAL '5 minutes'
                        ORDER BY hostname
                    """)
                    nodes = cur.fetchall()
                    
                    cur.execute("SELECT COUNT(*) as cnt FROM failed_files")
                    failures = cur.fetchone()['cnt']
            finally:
                conn.close()
        return nodes, failures

    def report_failure(self, filename, reason="Crash/Fail", log=""):
        sql = """
        INSERT INTO failed_files (filename, reason, log, reported_at) 
        VALUES (%s, %s, %s, NOW()) 
        ON CONFLICT (filename) 
        DO UPDATE SET reason = EXCLUDED.reason, log = EXCLUDED.log, reported_at = NOW()
        """
        conn = self.get_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (filename, reason, log))
                    print(f"Reported Failure: {filename[:15]}...")
            finally:
                conn.close()

    def get_failed_files(self):
        conn = self.get_conn()
        files = set()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT filename FROM failed_files")
                    for row in cur.fetchall():
                        files.add(row[0])
            finally:
                conn.close()
        return files

    def get_worker_settings(self):
        """Fetches all worker settings from the database."""
        settings = {}
        conn = self.get_conn()
        if conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT key, value FROM worker_settings")
                    for row in cur.fetchall():
                        settings[row['key']] = row['value']
            except Exception as e:
                print(f"DB Error fetching settings: {e}")
            finally:
                conn.close()
        return settings

    def get_node_command(self, hostname):
        """Fetches the status for a specific node, which can act as a command."""
        settings = {}
        conn = self.get_conn()
        if conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT status FROM active_nodes WHERE hostname = %s", (hostname,))
                    result = cur.fetchone()
                    return result['status'] if result else 'idle'
            finally:
                conn.close()
        return settings

    def clear_node(self):
        conn = self.get_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM active_nodes WHERE hostname = %s", (HOSTNAME,))
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
    if "cuda" in hw_out and "hevc_nvenc" in enc_out:
        print("✅ Found NVIDIA")
        return get_hw_config("nvidia")

    # --- Check 2: VAAPI (Intel/AMD on Linux) ---
    if "vaapi" in hw_out and "hevc_vaapi" in enc_out and sys.platform.startswith('linux'):
        print("✅ Found VAAPI")
        return get_hw_config("vaapi")
        
    return get_hw_config("cpu")

# ===========================
# Worker Logic
# ===========================

def get_media_info(filepath):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(filepath)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        # Find all video streams
        video_streams = [s for s in data.get('streams', []) if s['codec_type'] == 'video']
        if not video_streams:
            return None

        # Select the stream with the largest resolution (width * height)
        # This handles cases with embedded low-res album art.
        main_video_stream = max(video_streams, key=lambda s: s.get('width', 0) * s.get('height', 0))

        return {
            'codec': main_video_stream.get('codec_name'),
            'width': int(main_video_stream.get('width', 0)),
            'height': int(main_video_stream.get('height', 0)),
            'duration': float(data['format'].get('duration', 0)),
            'size': int(data['format'].get('size', 0)),
            'stream_index': main_video_stream.get('index')
        }
    except (subprocess.CalledProcessError, json.JSONDecodeError, StopIteration):
        # Handle cases where ffprobe fails or file is not valid media
        return None

def run_with_progress(cmd, total_duration, db, filename, hw_settings):
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', errors='replace', env=os.environ)
    pattern = re.compile(r"fps=\s*(\d+).*time=(\d{2}):(\d{2}):(\d{2}\.\d+).*speed=\s*([\d\.]+)x")
    
    last_update = 0
    err_log = [] 
    is_paused = False

    try:
        while True:
            if STOP_EVENT.is_set():
                process.kill()
                return -999, "Stopped by user command"

            # --- Pause/Resume Logic ---
            command = db.get_node_command(HOSTNAME)
            if command == 'paused' and not is_paused:
                print("\n⏸️ Pausing transcode...")
                process.send_signal(signal.SIGSTOP)
                is_paused = True
                db.update_heartbeat("Paused", hw_settings['codec'], int(percent) if 'percent' in locals() else 0, "0", VERSION, status='paused')
            elif command == 'running' and is_paused:
                print("\n▶️ Resuming transcode...")
                process.send_signal(signal.SIGCONT)
                is_paused = False
            
            if is_paused:
                time.sleep(2) # While paused, check for resume command every 2 seconds
                continue

            char = process.stderr.read(1)
            if not char and process.poll() is not None: break
            if char != '\r' and char != '\n': 
                err_log.append(char)
                continue
            
            line = "".join(err_log[-200:])
            if not line: continue

            match = pattern.search(line)
            if match:
                fps = match.group(1)
                h, m, s = map(float, match.groups()[1:4])
                speed = match.group(5)
                curr_seconds = h*3600 + m*60 + s
                percent = (curr_seconds / total_duration) * 100
                
                print(f"\r🚀 {filename[:30]:<30} | {percent: >5.1f}% | {speed}x | FPS: {fps} ", end="", flush=True)
                
                err_log = [] 

                if time.time() - last_update > 2:
                    db.update_heartbeat(filename, hw_settings['codec'], int(percent), speed, VERSION)
                    last_update = time.time()

        remainder = process.stderr.read()
        full_log = "".join(err_log) + remainder
        return process.returncode, full_log
    except Exception as e:
        process.kill()
        return -1, str(e)

def get_cq_value(width, hw_type, settings):
    is_hd = width >= int(settings.cq_width_threshold)
    if hw_type == "nvidia":
        return settings.nvenc_cq_hd if is_hd else settings.nvenc_cq_sd
    elif hw_type == "intel":
        return settings.vaapi_cq_hd if is_hd else settings.vaapi_cq_sd
    else:
        return settings.cpu_cq_hd if is_hd else settings.cpu_cq_sd

def worker_loop(root, db, cli_args):
    print(f"🚀 Node Online: {HOSTNAME}")

    # --- Initial Hardware Detection ---
    # Fetch settings once at the start to determine which hardware to probe.
    initial_settings = db.get_worker_settings()
    accel_mode = initial_settings.get('hardware_acceleration', 'auto')
    hw_settings = detect_hardware_settings(accel_mode)
    print(f"⚙️  Detected Encoder: {hw_settings['codec']}")

    # --- Initial State: Idle ---
    # The node joins the cluster in an idle state and waits for a 'start' command.
    db.update_heartbeat("Idle (Awaiting Start)", "N/A", 0, "0", VERSION, status='idle')
    while not STOP_EVENT.is_set():
        command = db.get_node_command(HOSTNAME)
        if command == 'running':
            print("Start command received. Beginning main worker loop.")
            break
        STOP_EVENT.wait(5) # Check for command every 5 seconds

    # --- Main Watcher Loop ---
    while not STOP_EVENT.is_set():
        files_processed_this_scan = 0

        # Fetch the latest settings at the start of each full scan
        settings_raw = db.get_worker_settings()

        # Check if command-line debug flag is set. If so, it overrides the DB setting.
        db_debug = settings_raw.get('debug', 'false').lower() == 'true'
        is_debug_mode = cli_args.debug or db_debug
        
        # Define a simple structure for settings
        WorkerArgs = namedtuple('WorkerArgs', settings_raw.keys())
        args = WorkerArgs(
            rescan_delay_minutes=int(settings_raw.get('rescan_delay_minutes', 5)),
            skip_encoded_folder=settings_raw.get('skip_encoded_folder', 'true').lower() == 'true',
            min_length=float(settings_raw.get('min_length', 1.5)),
            recursive_scan=settings_raw.get('recursive_scan', 'true').lower() == 'true',
            keep_original=settings_raw.get('keep_original', 'false').lower() == 'true',
            backup_directory=settings_raw.get('backup_directory', ''),
            allow_hevc=settings_raw.get('allow_hevc', 'false').lower() == 'true',
            allow_av1=settings_raw.get('allow_av1', 'false').lower() == 'true',
            hardware_acceleration=settings_raw.get('hardware_acceleration', 'auto'),
            auto_update=settings_raw.get('auto_update', 'true').lower() == 'true',
            clean_failures=settings_raw.get('clean_failures', 'false').lower() == 'true',
            debug=is_debug_mode,
            nvenc_cq_hd=settings_raw.get('nvenc_cq_hd', '32'),
            nvenc_cq_sd=settings_raw.get('nvenc_cq_sd', '28'),
            vaapi_cq_hd=settings_raw.get('vaapi_cq_hd', '28'),
            vaapi_cq_sd=settings_raw.get('vaapi_cq_sd', '24'),
            cpu_cq_hd=settings_raw.get('cpu_cq_hd', '28'),
            cpu_cq_sd=settings_raw.get('cpu_cq_sd', '24'),
            cq_width_threshold=settings_raw.get('cq_width_threshold', '1900'),
            extensions=settings_raw.get('extensions', '.mkv,.mp4')
        )
        allowed_extensions = {ext.strip() for ext in args.extensions.split(',')}

        # Report that the node is starting a scan
        db.update_heartbeat("Scanning for files...", "N/A", 0, "0", VERSION, status='running')
        
        # Get a fresh list of failed files for each scan
        global_failures = db.get_failed_files()
        
        # Get a fresh iterator for each scan
        iterator = os.walk(root) if args.recursive_scan else [(str(root), [], os.listdir(root))]

        for dirpath, dirnames, filenames in iterator:
            if STOP_EVENT.is_set(): break

            if skip_encoded_folder and 'encoded' in dirnames:
                dirnames.remove('encoded') # This stops os.walk from descending into it

            dir_path = Path(dirpath)
            for fname in filenames:
                if STOP_EVENT.is_set(): break
                fpath = dir_path / fname
                
                # --- Filtering Checks ---
                if fpath.suffix.lower() not in allowed_extensions: 
                    if args.debug: print(f"DEBUG: Skip: {fname} (Extension)")
                    continue
                
                if fname in global_failures:
                    if args.debug: print(f"DEBUG: Skip: {fname} (Global Fail)")
                    continue

                lock_file = fpath.with_suffix('.lock')
                if lock_file.exists(): 
                    if args.debug: print(f"DEBUG: Skip: {fname} (Locked)")
                    continue 
                    
                if (dir_path / "encoded.list").exists():
                    try:
                        if fname in (dir_path / "encoded.list").read_text().splitlines():
                            if args.debug: print(f"DEBUG: Skip: {fname} (Local History)")
                            continue
                    except: pass

                info = get_media_info(fpath)
                if not info or (info['duration'] / 60) < args.min_length:
                    if args.debug: print(f"DEBUG: Skip: {fname} (Too short or not media)")
                    continue
                # --- End Filtering Checks ---

                try:
                    # Attempt to lock (claim file)
                    with open(lock_file, 'w') as f: f.write(HOSTNAME)
                except: 
                    # Failed to lock (e.g., permissions issue)
                    continue
                
                if args.debug: print(f"DEBUG: Lock Acquired: {fname}")
                files_processed_this_scan += 1

                try:
                    should_skip = False
                    if not info: 
                        if args.debug: print(f"DEBUG: Skip: {fname} (FFprobe failed)")
                        should_skip = True
                    elif info['codec'] == 'hevc' and not args.allow_hevc: 
                        if args.debug: print(f"DEBUG: Skip: {fname} (HEVC codec, not allowed)")
                        should_skip = True
                    elif info['codec'] == 'av1' and not args.allow_av1: 
                        if args.debug: print(f"DEBUG: Skip: {fname} (AV1 codec, not allowed)")
                        should_skip = True

                    if should_skip:
                        lock_file.unlink()
                        continue

                    print(f"\n✅ [Accepted] {fname}")
                    if args.debug: print(f"DEBUG: Processing: {fname}")

                    cq = get_cq_value(info['width'], hw_settings['type'], args)
                    temp_out = dir_path / f".tmp_{fpath.stem}.mkv"
                    
                    cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-stats']
                    cmd.extend(hw_settings["hw_pre_args"])
                    cmd.extend(['-i', str(fpath)])
                    cmd.extend(['-map', f"0:{info['stream_index']}", '-map', '0:a?', '-map', '0:s?'])
                    cmd.extend(['-c:v', hw_settings["codec"]])
                    if hw_settings["preset"]: cmd.extend(['-preset', hw_settings["preset"]])
                    cmd.extend([hw_settings["cq_flag"], str(cq)] + hw_settings["extra"])
                    cmd.extend(['-c:a', 'aac', '-b:a', '256k'])
                    cmd.extend(['-c:s', 'copy', str(temp_out)])

                    if args.debug:
                        # Print the full command for debugging purposes
                        print(f"\nDEBUG: Running command:\n{' '.join(cmd)}\n")

                    # Start FFmpeg subprocess
                    ret, err_log = run_with_progress(cmd, info['duration'], db, fname, hw_settings)

                    # --- Naming Logic ---
                    hw_tag = 'NVENC' if hw_settings['type'] == 'nvidia' else 'VAAPI'
                    new_filename_base = f"{fpath.stem}.{hw_tag}.mkv"


                    # --- Post-Processing ---
                    if ret == 0:
                        if temp_out.exists() and temp_out.stat().st_size < info['size']:                        
                            finalize_file(db, fpath, temp_out, new_filename_base, info['size'], args.keep_original, args.backup_directory, HOSTNAME, hw_settings['codec'])
                            with open(dir_path / "encoded.list", "a") as f: f.write(f"{fname}\n")
                            db.clear_node() 
                            print("\n✅ Finished.")

                        else:
                            if args.debug: print(f"DEBUG: Discarded: {fname} (Too Large or Missing Output)")
                            if temp_out.exists(): temp_out.unlink()
                            with open(dir_path / "encoded.list", "a") as f: f.write(f"{fname}\n")
                            print("\n⚠️ Larger or missing output, discarded.")

                    else:
                        # --- Fallback and Crash Reporting ---
                        if "minimum supported value" in err_log and hw_settings['type'] != 'cpu':
                            print(f"\n⚠️  HW encode failed for low resolution. Falling back to CPU for {fname}...")
                            cpu_hw_settings = get_hw_config("cpu") # This is fine, it's just a struct
                            cpu_cq = get_cq_value(info['width'], cpu_hw_settings['type'], args)
                            
                            cmd[cmd.index(hw_settings['codec'])] = cpu_hw_settings['codec']
                            cmd[cmd.index(str(cq))] = str(cpu_cq)
                            
                            ret, err_log = run_with_progress(cmd, info['duration'], db, fname, cpu_hw_settings, VERSION)

                            if ret == 0 and temp_out.exists() and temp_out.stat().st_size < info['size']:
                                finalize_file(db, fpath, temp_out, new_filename_base, info['size'], args.keep_original, args.backup_directory, HOSTNAME, cpu_hw_settings['codec'])
                                print("\n✅ Finished (CPU Fallback).")
                            else:
                                report_and_log_failure(fname, ret, err_log, db, global_failures, temp_out)
                        else:
                            report_and_log_failure(fname, ret, err_log, db, global_failures, temp_out)


                except Exception as e:
                    print(f"Fatal Error on {fname}: {e}")
                finally:
                    if lock_file.exists(): lock_file.unlink()
                    if args.debug: print(f"DEBUG: Lock Released: {fname}")
        
        if STOP_EVENT.is_set():
            break

        # Unified wait logic at the end of every scan cycle.
        db.update_heartbeat("Idle", "N/A", 0, "0", VERSION, status='running')
        wait_seconds = args.rescan_delay_minutes * 60

        # If the delay is 0, we still wait a short time to prevent a tight loop that consumes CPU.
        if wait_seconds <= 0:
            wait_seconds = 60 # Default to 60 seconds if delay is 0 or less.

        # Before waiting, check if a stop command has been issued.
        command = db.get_node_command(HOSTNAME)
        if command == 'idle':
            print("\n⏹️ Stop command received. Returning to idle state.")
            db.update_heartbeat("Idle (Awaiting Start)", "N/A", 0, "0", VERSION, status='idle')
            break # Exit the processing loop and go back to the initial idle/wait loop.
        
        print(f"\n🏁 Scan complete. Next scan in {wait_seconds / 60:.0f} minute(s)...")
        STOP_EVENT.wait(wait_seconds)

    print("\nWatcher stopped.")
    db.clear_node() 

def finalize_file(db, original_path, temp_path, new_filename_base, original_size, keep_original, backup_dir, hostname, codec):
    """Handles file operations for a successful transcode."""
    # if args.debug: print(f"DEBUG: Encode Success, Finalizing {original_path.name}")
    
    if keep_original:
        # Log success before moving the file
        db.report_success(original_path.name, hostname, codec, original_size, temp_path.stat().st_size)

        encoded_dir = original_path.parent / "encoded"
        encoded_dir.mkdir(exist_ok=True)
        new_name = encoded_dir / new_filename_base
        shutil.move(temp_path, new_name)
    else:
        if backup_dir:
            backup_path = Path(backup_dir)
            backup_path.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original_path, backup_path / original_path.name)
        
        # Log success before moving the file
        db.report_success(original_path.name, hostname, codec, original_size, temp_path.stat().st_size)

        target_tagged_mkv = original_path.parent / new_filename_base
        shutil.move(temp_path, target_tagged_mkv)
        
        if original_path.suffix != target_tagged_mkv.suffix or original_path.name != target_tagged_mkv.name: 
            original_path.unlink()

def report_and_log_failure(filename, exit_code, log, db, failure_set, temp_file):
    """Consolidates failure reporting and logging."""
    if temp_file.exists():
        try:
            temp_file.unlink()
        except OSError:
            pass
            
    reason = f"FFmpeg exited with code {exit_code}"
    db.report_failure(filename, reason=reason, log=log)
    failure_set.add(filename)

    print(f"\n❌ CRASH REPORT FOR {filename}: {reason}. Log saved to database.")
    print("-" * 40)


def check_for_updates(auto_update=False):
    """Checks GitHub for a newer version of the script and prompts to update."""
    print(f"Worker Version: {VERSION}")
    version_url = "https://raw.githubusercontent.com/m1ckyb/CluserEncode/develop/VERSION.txt"
    script_url = f"https://raw.githubusercontent.com/m1ckyb/CluserEncode/develop/worker/transcode.py"

    try:
        with urllib.request.urlopen(version_url) as response:
            remote_version = response.read().decode('utf-8').strip()

        # Simple version comparison
        if remote_version > VERSION:
            print(f"✨ A new version is available: {remote_version}")

            if auto_update:
                print("Downloading update...")
                with urllib.request.urlopen(script_url) as response:
                    new_script_content = response.read()

                script_path = Path(__file__).resolve()
                with open(script_path, 'wb') as f:
                    f.write(new_script_content)
                
                print("✅ Update successful! Please run the script again.")
                sys.exit(0)
            else:
                print("Skipping update. To update, run with the --update flag.")

    except Exception as e:
        print(f"⚠️  Could not check for updates: {e}")

# ===========================
# Main Execution
# ===========================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", help="The root folder to scan for videos.")
    parser.add_argument("--update", action="store_true", help="Check for updates and exit.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging, overriding the database setting.")
    args = parser.parse_args()

    # Perform self-update check before doing anything else
    if args.update:
        check_for_updates(auto_update=True)
        sys.exit(0)
    else:
        check_for_updates(auto_update=False)

    # Connect to DB using centralized config
    db = DatabaseHandler(DB_CONFIG)
    if not db.get_conn():
        sys.exit(1)

    # --- Worker Thread Setup ---
    root = Path(args.folder).resolve()
    
    # All other settings are now fetched from the database inside the loop.
    # We pass the command-line args to allow for overrides like --debug.
    worker_thread = threading.Thread(target=worker_loop, args=(root, db, args))
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