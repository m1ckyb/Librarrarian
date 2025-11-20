import os
import sys
import time
from datetime import datetime
from flask import Flask, render_template, g, request, flash, redirect, url_for
from flask import jsonify
# Check for Postgres Driver
try:
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
    "dbname": os.environ.get("DB_NAME", "transcode_cluster")
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
            cur.execute("""
                SELECT *, EXTRACT(EPOCH FROM (NOW() - last_updated)) as age 
                FROM active_nodes 
                WHERE last_updated > NOW() - INTERVAL '5 minutes'
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
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT key, value, description FROM worker_settings")
            for row in cur.fetchall():
                settings[row['key']] = row
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
            cur.execute(
                "UPDATE worker_settings SET value = %s, updated_at = NOW() WHERE key = %s",
                (value, key)
            )
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
                "UPDATE active_nodes SET status = %s, last_updated = NOW() WHERE hostname = %s;",
                (status, hostname)
            )
            # The above command will not fail if the node doesn't exist, but it also won't update anything.
            # We check rowcount to see if a change was made.
            if cur.rowcount == 0:
                # If no rows were updated, it means the node isn't in the table yet.
                # This can happen if a worker is stopped before its first heartbeat.
                # We'll insert it with the desired status.
                cur.execute(
                    "INSERT INTO active_nodes (hostname, status, file, last_updated) VALUES (%s, %s, 'N/A', NOW()) ON CONFLICT (hostname) DO NOTHING;",
                    (hostname, status)
                )
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
        codec = node.get('codec', '')
        if 'nvenc' in codec:
            node['color'] = 'success' # Green
        elif 'vaapi' in codec or 'qsv' in codec:
            node['color'] = 'primary' # Blue
        else:
            node['color'] = 'warning' # Yellow

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
            'nvenc_cq_hd': request.form.get('nvenc_cq_hd', '32'),
            'nvenc_cq_sd': request.form.get('nvenc_cq_sd', '28'),
            'vaapi_cq_hd': request.form.get('vaapi_cq_hd', '28'),
            'vaapi_cq_sd': request.form.get('vaapi_cq_sd', '24'),
            'cpu_cq_hd': request.form.get('cpu_cq_hd', '28'),
            'cpu_cq_sd': request.form.get('cpu_cq_sd', '24'),
            'cq_width_threshold': request.form.get('cq_width_threshold', '1900'),
            'extensions': request.form.get('extensions', '.mkv,.mp4'),
        }

        errors = []
        for key, value in settings_to_update.items():
            success, error = update_worker_setting(key, value)
            if not success:
                errors.append(error)

        if not errors:
            flash('Worker settings have been updated successfully!', 'success')
        else:
            flash(f'Failed to update some settings: {", ".join(errors)}', 'danger')
    
    # Redirect back to the main dashboard page after handling the POST request.
    return redirect(url_for('dashboard'))

@app.route('/api/status')
def api_status():
    """Returns cluster status data as JSON."""
    nodes, fail_count, db_error = get_cluster_status()
    
    # Add the color key for the frontend to use
    for node in nodes:
        codec = node.get('codec', '')
        if 'nvenc' in codec:
            node['color'] = 'success' # Green
        elif 'vaapi' in codec or 'qsv' in codec:
            node['color'] = 'primary' # Blue
        else:
            node['color'] = 'warning' # Yellow

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

if __name__ == '__main__':
    # Use host='0.0.0.0' to make the app accessible on your network
    app.run(debug=True, host='0.0.0.0', port=5000)
