import os
import sys
import time
from datetime import datetime
from flask import Flask, render_template, g
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

# Use the same DB config as the worker script
# It is recommended to use environment variables for sensitive data
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "192.168.10.120"),
    "user": os.environ.get("DB_USER", "transcode"),
    "password": os.environ.get("DB_PASSWORD"),
    "dbname": os.environ.get("DB_NAME", "transcode_cluster")
}

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
    nodes, fail_count, db_error = get_cluster_status()
    
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
        db_error=db_error,
        last_updated=datetime.now().strftime('%H:%M:%S')
    )

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
