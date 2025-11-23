import os
import sys
import time
import threading
import uuid
from datetime import datetime
from plexapi.myplex import MyPlexAccount, MyPlexPinLogin
from flask import Flask, render_template, g, request, flash, redirect, url_for
from flask import jsonify

try:
    from plexapi.server import PlexServer
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("❌ Error: Missing required packages for the web dashboard.")
    print("   Please run: pip install Flask psycopg2-binary")
    sys.exit(1)
# ===========================
# Configuration
# ===========================
app = Flask(__name__)
# A secret key is required for session management (e.g., for flash messages)
# It's recommended to set this as an environment variable in production.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a-super-secret-key-for-dev")

# Use the same DB config as the worker script
# It is recommended to use environment variables for sensitive data
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "192.168.10.120"),
    "user": os.environ.get("DB_USER", "transcode"),
    "password": os.environ.get("DB_PASSWORD"),
    "dbname": os.environ.get("DB_NAME", "codecshift")
}

def get_project_version():
    """Reads the version from the root VERSION.txt file."""
    try:
        version_file = os.path.join(os.path.dirname(__file__), '..', 'VERSION.txt')
        return open(version_file, 'r').read().strip()
    except FileNotFoundError:
        return "unknown"


# ===========================
# Database Layer
# ===========================
def get_db():
    """Opens a new database connection if there is none yet for the current application context."""
    if 'db' not in g:
        try:
            g.db = psycopg2.connect(**DB_CONFIG)
        except psycopg2.OperationalError:
            g.db = None # Fail gracefully if DB is down
    return g.db


@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'db') and g.db is not None:
        g.db.close()


def init_db():
    """Initializes the database and creates all necessary tables if they don't exist."""
    conn = get_db()
    if not conn:
        print("DB Init Error: Could not connect to database.")
        return

    with conn.cursor() as cur:
        # Renamed from active_nodes to nodes for clarity
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id SERIAL PRIMARY KEY,
                hostname VARCHAR(255) UNIQUE NOT NULL,
                status VARCHAR(50),
                last_heartbeat TIMESTAMP,
                version VARCHAR(50),
                command VARCHAR(50) DEFAULT 'idle',
                progress REAL,
                fps REAL,
                current_file TEXT
            );
        """)
        # New table for the job queue
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                filepath TEXT NOT NULL UNIQUE,
                job_type VARCHAR(20) NOT NULL DEFAULT 'transcode',
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                assigned_to VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS worker_settings (
                id SERIAL PRIMARY KEY,
                setting_name VARCHAR(255) UNIQUE NOT NULL,
                setting_value TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS encoded_files (
                id SERIAL PRIMARY KEY,
                filename TEXT,
                original_size BIGINT,
                new_size BIGINT,
                encoded_by TEXT,
                encoded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS failed_files (
                id SERIAL PRIMARY KEY,
                filename TEXT,
                reason TEXT,
                log TEXT,
                failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    conn.commit()

def get_cluster_status():
    """Fetches node and failure data from the database."""
    db = get_db()
    nodes = []
    failures = 0
    db_error = None

    if db is None:
        db_error = "Cannot connect to the PostgreSQL database."
        return nodes, failures, db_error

    try:
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            # Get active nodes (updated in the last 5 minutes)
            # Using the new 'nodes' table schema
            cur.execute("""
                SELECT *, EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as age
                FROM nodes
                WHERE last_heartbeat > NOW() - INTERVAL '5 minutes'
                ORDER BY hostname
            """)
            nodes = cur.fetchall()
            
            # Get total failure count
            cur.execute("SELECT COUNT(*) as cnt FROM failed_files")
            failures = cur.fetchone()['cnt']
    except Exception as e:
        db_error = f"Database query failed: {e}"

    return nodes, failures, db_error

def get_failed_files_list():
    """Fetches the detailed list of failed files from the database."""
    db = get_db()
    files = []
    db_error = None

    if db is None:
        db_error = "Cannot connect to the PostgreSQL database."
        return files, db_error
    
    try:
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT filename, reason, reported_at, log FROM failed_files ORDER BY reported_at DESC")
            files = cur.fetchall()
    except Exception as e:
        db_error = f"Database query failed: {e}"

    return files, db_error

def clear_failed_files():
    """Clears all entries from the failed_files table."""
    db = get_db()
    db_error = None

    if db is None:
        db_error = "Cannot connect to the PostgreSQL database."
        return db_error
    
    try:
        with db.cursor() as cur:
            cur.execute("TRUNCATE TABLE failed_files")
        db.commit()
    except Exception as e:
        db_error = f"Database query failed: {e}"
    return db_error

def get_worker_settings():
    """Fetches all worker settings from the database."""
    db = get_db()
    settings = {}
    db_error = None
    if db is None:
        db_error = "Cannot connect to the PostgreSQL database."
        return settings, db_error
    try:
        # Using new settings table schema
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT setting_name, setting_value, 'description' as description FROM worker_settings")
            for row in cur.fetchall():
                settings[row['setting_name']] = row
    except Exception as e:
        db_error = f"Database query failed: {e}"
    return settings, db_error

def update_worker_setting(key, value):
    """Updates a specific worker setting in the database."""
    db = get_db()
    db_error = None
    if db is None:
        db_error = "Cannot connect to the PostgreSQL database."
        return False, db_error
    try:
        with db.cursor() as cur:
            # Use an "upsert" to either insert a new setting or update an existing one.
            # This prevents errors on a fresh database where the settings rows don't exist yet.
            cur.execute("""
                INSERT INTO worker_settings (setting_name, setting_value)
                VALUES (%s, %s)
                ON CONFLICT (setting_name) DO UPDATE
                SET setting_value = EXCLUDED.setting_value;
            """, (key, value))
        db.commit()
    except Exception as e:
        db_error = f"Database query failed: {e}"
        try:
            db.rollback()
        except:
            pass
        return False, db_error
    return True, None

def set_node_status(hostname, status):
    """Sets the status of a specific node (e.g., to 'running')."""
    db = get_db()
    db_error = None
    if db is None:
        db_error = "Cannot connect to the PostgreSQL database."
        return False, db_error
    try:
        with db.cursor() as cur:
            cur.execute(
                "UPDATE nodes SET command = %s, last_heartbeat = NOW() WHERE hostname = %s;",
                (status, hostname)
            )
            # The above command will not fail if the node doesn't exist, but it also won't update anything.
            # We check rowcount to see if a change was made.
            if cur.rowcount == 0:
                # If no rows were updated, it means the node isn't in the table yet.
                # This can happen if a worker is controlled before its first heartbeat.
                # We'll insert it with the desired status.
                # Corrected to insert into the 'nodes' table
                cur.execute("""
                    INSERT INTO nodes (hostname, status, command, last_heartbeat) VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (hostname) DO NOTHING;
                """, (hostname, status, status))
        db.commit()
    except Exception as e:
        db_error = f"Database query failed: {e}"
        return False, db_error
    return True, None
# ===========================
# History Functions
# ===========================

def get_history():
    """Fetches the last 100 successfully encoded files."""
    db = get_db()
    history = []
    db_error = None
    if db is None:
        db_error = "Cannot connect to the PostgreSQL database."
        return history, db_error
    try:
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM encoded_files ORDER BY encoded_at DESC LIMIT 100")
            history = cur.fetchall()
    except Exception as e:
        db_error = f"Database query failed: {e}"
    return history, db_error
# ===========================
# Flask Routes
# ===========================
@app.route('/')
def dashboard():
    """Renders the main dashboard page."""
    # Fetch cluster status and worker settings
    nodes, fail_count, db_error = get_cluster_status()
    settings, settings_db_error = get_worker_settings()

    # Add a 'color' key for easy templating
    for node in nodes:
        # This logic is now handled on the frontend, but we can keep it as a fallback
        # A better approach would be to determine color based on status ('encoding', 'idle', etc.)
        if node.get('status') == 'encoding':
            node['color'] = 'success'
        elif node.get('status') == 'idle':
            node['color'] = 'secondary'
        else: node['color'] = 'warning'

    return render_template(
        'index.html', 
        nodes=nodes, 
        fail_count=fail_count, 
        db_error=db_error or settings_db_error, # Show error from either query
        settings=settings,
        last_updated=datetime.now().strftime('%H:%M:%S'),
        version=get_project_version()
    )

@app.route('/options', methods=['GET', 'POST'])
def options():
    """
    Handles the form submission for worker settings from the main dashboard.
    The GET method is no longer used as the form is on the main page.
    """
    if request.method == 'POST':
        # A dictionary to hold all settings from the form
        settings_to_update = {
            'rescan_delay_minutes': request.form.get('rescan_delay_minutes', '5'),
            'min_length': request.form.get('min_length', '1.5'),
            'backup_directory': request.form.get('backup_directory', ''),
            'hardware_acceleration': request.form.get('hardware_acceleration', 'auto'),
            # Checkboxes return 'true' if checked, otherwise they are not in the form data
            'recursive_scan': 'true' if 'recursive_scan' in request.form else 'false',
            'skip_encoded_folder': 'true' if 'skip_encoded_folder' in request.form else 'false',
            'keep_original': 'true' if 'keep_original' in request.form else 'false',
            'allow_hevc': 'true' if 'allow_hevc' in request.form else 'false',
            'allow_av1': 'true' if 'allow_av1' in request.form else 'false',
            'auto_update': 'true' if 'auto_update' in request.form else 'false',
            'clean_failures': 'true' if 'clean_failures' in request.form else 'false',
            'debug': 'true' if 'debug' in request.form else 'false',
            # Advanced settings
            'plex_url': request.form.get('plex_url', ''),
            'nvenc_cq_hd': request.form.get('nvenc_cq_hd', '32'),
            'nvenc_cq_sd': request.form.get('nvenc_cq_sd', '28'),
            'vaapi_cq_hd': request.form.get('vaapi_cq_hd', '28'),
            'vaapi_cq_sd': request.form.get('vaapi_cq_sd', '24'),
            'cpu_cq_hd': request.form.get('cpu_cq_hd', '28'),
            'cpu_cq_sd': request.form.get('cpu_cq_sd', '24'),
            'cq_width_threshold': request.form.get('cq_width_threshold', '1900'),
        }

        # Handle multi-select for Plex libraries
        plex_libraries = request.form.getlist('plex_libraries')
        settings_to_update['plex_libraries'] = ','.join(plex_libraries)

        errors = []
        for key, value in settings_to_update.items():
            success, error = update_worker_setting(key, value)
            if not success:
                errors.append(error)

        if not errors:
            flash('Worker settings have been updated successfully!', 'success')
        else:
            flash(f'Failed to update some settings: {", ".join(errors)}', 'danger')
    
    # Instead of redirecting (which can cause race conditions),
    # re-fetch all data and render the template directly.
    # This ensures the UI has the absolute latest settings.
    nodes, fail_count, db_error = get_cluster_status()
    settings, settings_db_error = get_worker_settings()
    return render_template(
        'index.html',
        nodes=nodes,
        fail_count=fail_count,
        db_error=db_error or settings_db_error,
        settings=settings
    )

@app.route('/api/status')
def api_status():
    """Returns cluster status data as JSON."""
    nodes, fail_count, db_error = get_cluster_status()
    
    # Add the color key for the frontend to use
    for node in nodes:
        # Simplified color logic based on status
        if node.get('status') == 'encoding':
            node['color'] = 'success'
        elif node.get('status') == 'idle':
            node['color'] = 'secondary'
        else:
            node['color'] = 'warning'

    return jsonify(
        nodes=nodes,
        fail_count=fail_count,
        db_error=db_error,
        last_updated=datetime.now().strftime('%H:%M:%S')
    )

@app.route('/api/failures', methods=['GET'])
def api_failures():
    """Returns the list of failed files as JSON."""
    files, db_error = get_failed_files_list()
    for file in files:
        file['reported_at'] = file['reported_at'].strftime('%Y-%m-%d %H:%M:%S')
    return jsonify(files=files, db_error=db_error)

@app.route('/api/failures/clear', methods=['POST'])
def api_clear_failures():
    """Clears the failed_files table."""
    db_error = clear_failed_files()
    if db_error:
        return jsonify(success=False, error=db_error), 500
    return jsonify(success=True, message="Failed files log has been cleared.")

@app.route('/api/nodes/<hostname>/start', methods=['POST'])
def api_start_node(hostname):
    """API endpoint to send a 'start' command to a node."""
    success, error = set_node_status(hostname, 'running')
    if not success:
        return jsonify(success=False, error=error), 500
    return jsonify(success=True, message=f"Start command sent to node '{hostname}'.")

@app.route('/api/nodes/<hostname>/stop', methods=['POST'])
def api_stop_node(hostname):
    """API endpoint to send a 'stop' (go to idle) command to a node."""
    success, error = set_node_status(hostname, 'idle')
    if not success:
        return jsonify(success=False, error=error), 500
    return jsonify(success=True, message=f"Stop command sent to node '{hostname}'.")

@app.route('/api/nodes/<hostname>/pause', methods=['POST'])
def api_pause_node(hostname):
    """API endpoint to send a 'pause' command to a node."""
    success, error = set_node_status(hostname, 'paused')
    if not success:
        return jsonify(success=False, error=error), 500
    return jsonify(success=True, message=f"Pause command sent to node '{hostname}'.")

@app.route('/api/nodes/<hostname>/resume', methods=['POST'])
def api_resume_node(hostname):
    """API endpoint to send a 'resume' command to a node."""
    success, error = set_node_status(hostname, 'running') # Resuming just sets it back to running
    if not success:
        return jsonify(success=False, error=error), 500
    return jsonify(success=True, message=f"Resume command sent to node '{hostname}'.")

@app.route('/api/history', methods=['GET'])
def api_history():
    """Returns the encoding history as JSON."""
    history, db_error = get_history()
    for item in history:
        # Format datetime and sizes for display
        item['encoded_at'] = item['encoded_at'].strftime('%Y-%m-%d %H:%M:%S')
        item['original_size_gb'] = round(item['original_size'] / (1024**3), 2)
        item['new_size_gb'] = round(item['new_size'] / (1024**3), 2)
        item['reduction_percent'] = round((1 - item['new_size'] / item['original_size']) * 100, 1) if item['original_size'] > 0 else 0
    return jsonify(history=history, db_error=db_error)

@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    """Truncates the encoded_files table to clear all history."""
    try:
        # Assuming you have a function like get_db() to get a database connection
        db = get_db() 
        with db.cursor() as cur:
            # TRUNCATE is faster than DELETE for clearing a whole table
            # RESTART IDENTITY resets the ID counter for the next entry
            cur.execute("TRUNCATE TABLE encoded_files RESTART IDENTITY;")
        db.commit()
        return jsonify(success=True)
    except Exception as e:
        # Log the error for debugging
        print(f"Error clearing history: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/history/delete/<int:entry_id>', methods=['POST'])
def delete_history_entry(entry_id):
    """Deletes a single entry from the encoded_files table."""
    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute("DELETE FROM encoded_files WHERE id = %s", (entry_id,))
        db.commit()
        if cur.rowcount == 0:
            return jsonify(success=False, error="Entry not found."), 404
        return jsonify(success=True)
    except Exception as e:
        print(f"Error deleting history entry {entry_id}: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/stats')
def api_stats():
    """Returns aggregate statistics and recent history."""
    db = get_db()
    stats = {}
    history = []
    db_error = None

    if db is None:
        db_error = "Cannot connect to the PostgreSQL database."
        return jsonify(stats={}, history=[], db_error=db_error)

    try:
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            # Get aggregate stats for completed files
            cur.execute("""
                SELECT
                    COUNT(*) AS total_files,
                    SUM(original_size) AS total_original_size,
                    SUM(new_size) AS total_new_size
                FROM encoded_files
                WHERE status = 'completed'
            """)
            agg_stats = cur.fetchone()

            # Get recent history (same as history tab)
            cur.execute("SELECT * FROM encoded_files WHERE status = 'completed' ORDER BY encoded_at DESC LIMIT 100")
            history = cur.fetchall()

        # Process stats for display
        total_original = agg_stats['total_original_size'] or 0
        total_new = agg_stats['total_new_size'] or 0
        stats = {
            'total_files': agg_stats['total_files'] or 0,
            'total_original_size_gb': round(total_original / (1024**3), 2),
            'total_new_size_gb': round(total_new / (1024**3), 2),
            'total_reduction_percent': round((1 - total_new / total_original) * 100, 1) if total_original > 0 else 0
        }

        # Process history for display
        for item in history:
            item['encoded_at'] = item['encoded_at'].strftime('%Y-%m-%d %H:%M:%S')
            item['original_size_gb'] = round(item['original_size'] / (1024**3), 2)
            item['new_size_gb'] = round(item['new_size'] / (1024**3), 2)
            item['reduction_percent'] = round((1 - item['new_size'] / item['original_size']) * 100, 1) if item['original_size'] > 0 else 0

    except Exception as e:
        db_error = f"Database query failed: {e}"

    return jsonify(stats=stats, history=history, db_error=db_error)

@app.route('/api/plex/login', methods=['POST'])
def plex_login():
    """Logs into Plex using username/password and saves the auth token."""
    username = request.json.get('username')
    password = request.json.get('password')

    if not username or not password:
        return jsonify(success=False, error="Username and password are required."), 400

    try:
        # Instantiate the account object with username and password to sign in.
        account = MyPlexAccount(username, password)
        token = account.authenticationToken
        if token:
            update_worker_setting('plex_token', token)
            return jsonify(success=True, message="Plex account linked successfully!")
        else:
            return jsonify(success=False, error="Login failed. Please check your credentials."), 401
    except Exception as e:
        return jsonify(success=False, error=f"Plex login failed: {e}"), 401

@app.route('/api/plex/logout', methods=['POST'])
def plex_logout():
    """Logs out of Plex by clearing the stored token."""
    success, error = update_worker_setting('plex_token', '')
    if success:
        return jsonify(success=True, message="Plex account unlinked.")
    else:
        return jsonify(success=False, error=error), 500

@app.route('/api/plex/libraries', methods=['GET'])
def plex_get_libraries():
    """Fetches a list of video libraries from the configured Plex server."""
    settings, _ = get_worker_settings()
    plex_url = settings.get('plex_url', {}).get('setting_value')
    plex_token = settings.get('plex_token', {}).get('setting_value')

    if not all([plex_url, plex_token]):
        return jsonify(libraries=[], error="Plex is not configured or authenticated."), 400

    try:
        plex = PlexServer(plex_url, plex_token)
        libraries = [
            {"title": section.title, "key": section.key}
            for section in plex.library.sections()
            if section.type == 'movie' or section.type == 'show'
        ]
        return jsonify(libraries=libraries)
    except Exception as e:
        return jsonify(libraries=[], error=f"Could not connect to Plex: {e}"), 500

# --- New Background Scanner and Worker API ---

def plex_scanner_thread():
    """Scans Plex libraries and adds non-HEVC files to the jobs table."""
    while True:
        try:
            with app.app_context():
                settings, db_error = get_worker_settings()
                if db_error:
                    print(f"[{datetime.now()}] Plex Scanner: Database not available. Retrying in 60s.")
                    time.sleep(60)
                    continue

                plex_url = settings.get('plex_url', {}).get('setting_value')
                plex_token = settings.get('plex_token', {}).get('setting_value')
                plex_libraries_str = settings.get('plex_libraries', {}).get('setting_value', '')
                plex_libraries = [lib.strip() for lib in plex_libraries_str.split(',') if lib.strip()]

                if not all([plex_url, plex_token, plex_libraries]):
                    # print("⚠️ Plex integration is not fully configured. The scanner will wait.")
                    time.sleep(60) # Wait and check again later
                    continue

                conn = get_db()
                cur = conn.cursor(cursor_factory=RealDictCursor)

                try:
                    plex_server = PlexServer(plex_url, plex_token)
                except Exception as e:
                    print(f"[{datetime.now()}] Plex Scanner: Could not connect to Plex server. Error: {e}")
                    time.sleep(300)
                    continue

                # Get existing files from jobs and history to avoid duplicates
                cur.execute("SELECT filepath FROM jobs")
                existing_jobs = {row['filepath'] for row in cur.fetchall()}
                cur.execute("SELECT filename FROM encoded_files")
                encoded_history = {row['filename'] for row in cur.fetchall()}
                
                new_files_found = 0
                print(f"[{datetime.now()}] Plex Scanner: Starting scan of libraries: {', '.join(plex_libraries)}")
                for lib_name in plex_libraries:
                    library = plex_server.library.section(title=lib_name)
                    print(f"[{datetime.now()}] Plex Scanner: Scanning '{library.title}'...")
                    for video in library.all():
                        # Check the codec of the main video stream
                        codec = video.media[0].video_codec
                        filepath = video.media[0].parts[0].file

                        if codec != 'hevc' and filepath not in existing_jobs and filepath not in encoded_history:
                            print(f"  -> Found non-HEVC file: {os.path.basename(filepath)} (Codec: {codec})")
                            cur.execute(
                                "INSERT INTO jobs (filepath, job_type, status) VALUES (%s, %s, %s) ON CONFLICT (filepath) DO NOTHING",
                                (filepath, 'transcode', 'pending')
                            )
                            new_files_found += 1
                
                conn.commit()
                if new_files_found > 0:
                    print(f"[{datetime.now()}] Plex Scanner: Added {new_files_found} new transcode jobs to the queue.")
                else:
                    print(f"[{datetime.now()}] Plex Scanner: Scan complete. No new files to add.")

                cur.close()
        except Exception as e:
            print(f"[{datetime.now()}] Scanner Error: {e}")
        
        # Wait for 5 minutes before the next scan
        time.sleep(300)

@app.route('/api/request_job', methods=['POST'])
def request_job():
    """Endpoint for workers to request a new job."""
    worker_hostname = request.json.get('hostname')
    if not worker_hostname:
        return jsonify({"error": "Hostname is required"}), 400

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("BEGIN;") # Start a transaction
        cur.execute("SELECT id, filepath, job_type FROM jobs WHERE status = 'pending' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED")
        job = cur.fetchone()

        if job:
            cur.execute("UPDATE jobs SET status = 'assigned', assigned_to = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (worker_hostname, job['id']))
            conn.commit()
            # Return the full job details to the worker
            return jsonify({"job_id": job['id'], "filepath": job['filepath'], "job_type": job['job_type']})
        else:
            conn.commit() # release lock
            return jsonify({}) # No pending jobs
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()

@app.route('/api/update_job/<int:job_id>', methods=['POST'])
def update_job(job_id):
    """Endpoint for workers to update the status of a job."""
    data = request.json
    status = data.get('status')  # 'completed' or 'failed'

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Fetch job details to know its type
    cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
    job = cur.fetchone()

    if not job:
        return jsonify({"error": "Job not found"}), 404

    if status == 'completed':
        if job['job_type'] == 'transcode':
            # For transcodes, move to encoded_files history
            cur.execute(
                "INSERT INTO encoded_files (filename, original_size, new_size, encoded_by, status) VALUES (%s, %s, %s, %s, 'completed')",
                (job['filepath'], data.get('original_size'), data.get('new_size'), job['assigned_to'])
            )
            # Trigger a Plex library scan
            try:
                settings, _ = get_worker_settings()
                plex_url = settings.get('plex_url', {}).get('setting_value')
                plex_token = settings.get('plex_token', {}).get('setting_value')
                if plex_url and plex_token:
                    plex = PlexServer(plex_url, plex_token)
                    # This is a simple approach; a more robust one would map file paths to libraries
                    print(f"[{datetime.now()}] Triggering Plex library update for all monitored libraries.")
                    plex.library.update()
            except Exception as e:
                print(f"⚠️ Could not trigger Plex scan: {e}")

        # For all completed jobs (transcode or cleanup), delete from the jobs queue
        cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        message = f"Job {job_id} ({job['job_type']}) completed and removed from queue."

    elif status == 'failed':
        # For any failed job, log it and mark as failed in the queue
        cur.execute("INSERT INTO failed_files (filename, reason, log) VALUES (%s, %s, %s)", (job['filepath'], data.get('reason'), data.get('log')))
        cur.execute("UPDATE jobs SET status = 'failed', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (job_id,))
        message = f"Job {job_id} ({job['job_type']}) failed and logged."

    conn.commit()
    cur.close()
    return jsonify({"message": message})


if __name__ == '__main__':
    scanner_thread = threading.Thread(target=plex_scanner_thread, daemon=True)
    scanner_thread.start()
    # Use host='0.0.0.0' to make the app accessible on your network
    app.run(debug=True, host='0.0.0.0', port=5000)

# Initialize the database when the application module is loaded.
with app.app_context():
    init_db()
