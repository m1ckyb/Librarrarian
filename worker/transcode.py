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
import json
from pathlib import Path
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

VERSION = "1.5-WebApp"
HOSTNAME = socket.gethostname()
STOP_EVENT = threading.Event()

# --- USER CONFIGURATION SECTION ---
# Read DB config from environment variables, with fallbacks for local testing
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "192.168.10.120"),
    "user": os.environ.get("DB_USER", "transcode"),
    "password": os.environ.get("DB_PASSWORD"),
    "dbname": os.environ.get("DB_NAME", "transcode_cluster")
}

CONFIG = {
    "NVENC_CQ_HD": "32",   
    "NVENC_CQ_SD": "28",   
    "VAAPI_CQ_HD": "28",   
    "VAAPI_CQ_SD": "24",   
    "CPU_CQ_HD": "28",
    "CPU_CQ_SD": "24",

    "CQ_WIDTH_THRESHOLD": 1900,
    "EXTENSIONS": {'.mkv', '.avi', '.mp4', '.mov', '.wmv', '.flv', '.m4v', '.ts', '.mpg', '.mpeg'}
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
        commands = [
            """
            CREATE TABLE IF NOT EXISTS active_nodes (
                hostname VARCHAR(255) PRIMARY KEY,
                file TEXT,
                codec VARCHAR(50),
                percent INTEGER,
                speed VARCHAR(50),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS failed_files (
                filename TEXT PRIMARY KEY,
                reason TEXT,
                reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        conn = self.get_conn()
        if conn:
            with conn.cursor() as cur:
                for cmd in commands:
                    cur.execute(cmd)
            conn.close()

    def update_heartbeat(self, filename, codec, percent, speed):
        sql = """
        INSERT INTO active_nodes (hostname, file, codec, percent, speed, last_updated)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (hostname) 
        DO UPDATE SET 
            file = EXCLUDED.file,
            codec = EXCLUDED.codec,
            percent = EXCLUDED.percent,
            speed = EXCLUDED.speed,
            last_updated = NOW();
        """
        conn = self.get_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (HOSTNAME, filename, codec, percent, speed))
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

    def report_failure(self, filename, reason="Crash/Fail"):
        sql = "INSERT INTO failed_files (filename, reason) VALUES (%s, %s) ON CONFLICT (filename) DO NOTHING"
        conn = self.get_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (filename, reason))
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

def detect_hardware_settings(args):
    if args.force_nvidia: return get_hw_config("nvidia")
    if args.force_qsv: return get_hw_config("qsv")
    if args.force_vaapi: return get_hw_config("vaapi")
    if args.force_cpu: return get_hw_config("cpu")

    print("🔍 Probing Hardware...", end=" ", flush=True)
    try:
        hw_out = subprocess.check_output(["ffmpeg", "-hide_banner", "-hwaccels"], text=True)
        enc_out = subprocess.check_output(["ffmpeg", "-hide_banner", "-encoders"], text=True)
    except:
        return get_hw_config("cpu")

    has_nvidia_dev = os.path.exists("/dev/nvidia0")
    has_render_dev = os.path.exists("/dev/dri/renderD128") 

    if has_nvidia_dev and "cuda" in hw_out and "hevc_nvenc" in enc_out:
        print("✅ Found NVIDIA")
        return get_hw_config("nvidia")

    if has_render_dev and "vaapi" in hw_out and "hevc_vaapi" in enc_out:
        print("✅ Found VAAPI")
        return get_hw_config("vaapi")
        
    return get_hw_config("cpu")

# ===========================
# Worker Logic
# ===========================

def get_media_info(filepath):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(filepath)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        video = next((s for s in data.get('streams', []) if s['codec_type'] == 'video'), None)
        if not video: return None
        return {
            'codec': video.get('codec_name'),
            'width': int(video.get('width', 0)),
            'height': int(video.get('height', 0)),
            'duration': float(data['format'].get('duration', 0)),
            'size': int(data['format'].get('size', 0))
        }
    except: return None

def run_with_progress(cmd, total_duration, db, filename, hw_settings):
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', errors='replace', env=os.environ)
    pattern = re.compile(r"fps=\s*(\d+).*time=(\d{2}):(\d{2}):(\d{2}\.\d+).*speed=\s*([\d\.]+)x")
    
    last_update = 0
    err_log = [] 

    try:
        while True:
            if STOP_EVENT.is_set():
                process.kill()
                return -999, "Stopped by user command"

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
                    db.update_heartbeat(filename, hw_settings['codec'], int(percent), speed)
                    last_update = time.time()

        remainder = process.stderr.read()
        full_log = "".join(err_log) + remainder
        return process.returncode, full_log
    except Exception as e:
        process.kill()
        return -1, str(e)

def get_cq_value(width, hw_type):
    is_hd = width >= CONFIG["CQ_WIDTH_THRESHOLD"]
    if hw_type == "nvidia":
        return CONFIG["NVENC_CQ_HD"] if is_hd else CONFIG["NVENC_CQ_SD"]
    elif hw_type == "intel":
        return CONFIG["VAAPI_CQ_HD"] if is_hd else CONFIG["VAAPI_CQ_SD"]
    else:
        return CONFIG["CPU_CQ_HD"] if is_hd else CONFIG["CPU_CQ_SD"]

def worker_loop(root, args, hw_settings, db):
    min_bytes = int(float(args.min.replace(',', '.')) * 1024**3) if args.min else 0
    
    print(f"🚀 Node Online: {HOSTNAME}")
    print(f"⚙️  Hardware: {hw_settings['codec']}")
    
    if args.debug:
        print(f"DEBUG: Starting Worker. HW: {hw_settings['codec']}")
        print(f"DEBUG: Min Size: {min_bytes / 1024**3:.2f} GB")

    iterator = os.walk(root) if args.recursive else [(str(root), [], os.listdir(root))]
    
    global_failures = db.get_failed_files()

    for dirpath, _, filenames in iterator:
        dir_path = Path(dirpath)
        for fname in filenames:
            if STOP_EVENT.is_set(): return
            fpath = dir_path / fname
            
            # --- Filtering Checks ---
            if fpath.suffix.lower() not in CONFIG["EXTENSIONS"]: 
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
                    
            if fpath.stat().st_size < min_bytes: 
                if args.debug: print(f"DEBUG: Skip: {fname} (Too Small)")
                continue
            # --- End Filtering Checks ---

            try:
                # Attempt to lock (claim file)
                with open(lock_file, 'w') as f: f.write(HOSTNAME)
            except: 
                # Failed to lock (e.g., permissions issue)
                continue
            
            if args.debug: print(f"DEBUG: Lock Acquired: {fname}")

            try:
                info = get_media_info(fpath)
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

                cq = get_cq_value(info['width'], hw_settings['type'])
                temp_out = dir_path / f".tmp_{fpath.stem}.mkv"
                
                cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-stats']
                cmd.extend(hw_settings["hw_pre_args"])
                cmd.extend(['-i', str(fpath)])
                cmd.extend(['-map', '0:v', '-map', '0:a?', '-map', '0:s?'])
                cmd.extend(['-c:v', hw_settings["codec"]])
                if hw_settings["preset"]: cmd.extend(['-preset', hw_settings["preset"]])
                cmd.extend([hw_settings["cq_flag"], str(cq)] + hw_settings["extra"])
                cmd.extend(['-c:a', 'aac', '-b:a', '256k'])
                cmd.extend(['-c:s', 'copy', str(temp_out)])

                # Start FFmpeg subprocess
                ret, err_log = run_with_progress(cmd, info['duration'], db, fname, hw_settings)

                # --- Naming Logic ---
                hw_tag = 'NVENC' if hw_settings['type'] == 'nvidia' else 'VAAPI'
                new_filename_base = f"{fpath.stem}.{hw_tag}.mkv"


                # --- Post-Processing ---
                if ret == 0:
                    if temp_out.exists() and temp_out.stat().st_size < info['size']:
                        if args.debug: print(f"DEBUG: Encode Success, Finalizing {fname}")
                        
                        if args.keep_original:
                            # Save to encoded/Subdir with TAGGED name
                            encoded_dir = dir_path / "encoded"
                            encoded_dir.mkdir(exist_ok=True)
                            new_name = encoded_dir / new_filename_base
                            shutil.move(temp_out, new_name)
                        else:
                            # Backup original file before overwriting
                            if args.backup:
                                backup_path = Path(args.backup)
                                backup_path.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(fpath, backup_path / fpath.name)
                            
                            # Overwrite/Replace the original file path with the TAGGED name
                            target_tagged_mkv = fpath.parent / new_filename_base
                            shutil.move(temp_out, target_tagged_mkv)
                            
                            # Delete the untagged original file
                            if fpath.suffix != target_tagged_mkv.suffix or fpath.name != target_tagged_mkv.name: 
                                fpath.unlink()
                            
                        with open(dir_path / "encoded.list", "a") as f: f.write(f"{fname}\n")
                        db.clear_node() 
                        print("\n✅ Finished.")

                    else:
                        if args.debug: print(f"DEBUG: Discarded: {fname} (Too Large or Missing Output)")
                        if temp_out.exists(): temp_out.unlink()
                        with open(dir_path / "encoded.list", "a") as f: f.write(f"{fname}\n")
                        print("\n⚠️ Larger or missing output, discarded.")

                else:
                    # --- CRASH REPORTING (Saves local log + reports to DB) ---
                    if temp_out.exists(): temp_out.unlink()
                    db.report_failure(fname)
                    global_failures.add(fname)

                    # 1. Write local error log for post-mortem debugging
                    log_dir = dir_path / ".transcode_logs"
                    log_dir.mkdir(exist_ok=True)
                    log_file_path = log_dir / f"{fname}.log"
                    with open(log_file_path, 'w') as f:
                        f.write(f"--- CRASH REPORT - {datetime.now()} ---\n")
                        f.write(f"FFmpeg exit code: {ret}\n")
                        f.write(f"Hardware used: {hw_settings['codec']}\n")
                        f.write("-" * 40 + "\n")
                        f.write(err_log)

                    # 2. Print summary to console (Always print crash, even if silent)
                    print(f"\n❌ CRASH REPORT FOR {fname}:")
                    print(f"   FFmpeg exit code: {ret}. LOG SAVED to: {log_file_path}")
                    print("-" * 40)
                    if args.debug: print(f"DEBUG: FFmpeg Failed: {fname} (Code {ret}). LOG SAVED.")


            except Exception as e:
                print(f"Fatal Error on {fname}: {e}")
            finally:
                if lock_file.exists(): lock_file.unlink()
                if args.debug: print(f"DEBUG: Lock Released: {fname}")
    
    print("\n🏁 Queue finished.")
    db.clear_node() 

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", help="Target folder to scan for videos.")
    
    parser.add_argument("--debug", action="store_true", help="Show verbose file rejection info")
    parser.add_argument("-R", "--recursive", action="store_true")
    parser.add_argument("-min", type=str)
    parser.add_argument("-keep-original", action="store_true")
    parser.add_argument("-backup", type=str)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--allow-hevc", action="store_true", help="Re-encode HEVC files")
    parser.add_argument("--allow-av1", action="store_true", help="Re-encode AV1 files")
    
    parser.add_argument("--force-nvidia", action="store_true", help="Force NVENC")
    parser.add_argument("--force-qsv", action="store_true", help="Force Intel QSV")
    parser.add_argument("--force-vaapi", action="store_true", help="Force VAAPI")
    parser.add_argument("--force-cpu", action="store_true", help="Force CPU (Slow)")
    
    args = parser.parse_args()

    # Connect to DB using centralized config
    db = DatabaseHandler(DB_CONFIG)
    if not db.get_conn():
        sys.exit(1)

    if args.clean:
        root = Path(args.folder).resolve()
        for f in root.rglob("*.lock"): f.unlink()
        print("🧹 Cleaned lock files.")
        sys.exit(0)

    # --- Worker Thread Setup ---
    hw_settings = detect_hardware_settings(args)
    root = Path(args.folder).resolve()
    
    worker_thread = threading.Thread(target=worker_loop, args=(root, args, hw_settings, db))
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