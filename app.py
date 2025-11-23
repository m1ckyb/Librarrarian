import os
import json
from flask import Flask, render_template, jsonify, request, flash, redirect, url_for
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor

# ==============================================================================
# App & DB Initialization
# ==============================================================================

app = Flask(__name__)

# Use environment variables for configuration with sensible defaults
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a-very-secret-key')

# --- Database Connection Pool ---
# Using a connection pool is more efficient than creating new connections for every request.
try:
    db_pool = SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        host=os.environ.get("DB_HOST", "db"),
        user=os.environ.get("POSTGRES_USER", "transcode"),
        password=os.environ.get("POSTGRES_PASSWORD", "password"),
        dbname=os.environ.get("POSTGRES_DB", "codecshift")
    )
except Exception as e:
    print(f"FATAL: Could not connect to database pool: {e}")
    db_pool = None

def get_db_conn():
    """Gets a connection from the pool."""
    if not db_pool:
        return None
    return db_pool.getconn()

def put_db_conn(conn):
    """Returns a connection to the pool."""
    if db_pool and conn:
        db_pool.putconn(conn)

# ==============================================================================
# API Endpoints
# ==============================================================================

@app.route('/api/status')
def api_status():
    """Provides a full status update for the frontend."""
    conn = get_db_conn()
    if not conn:
        return jsonify({"db_error": "Database connection pool is not available."}), 500

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Fetch active nodes
            cur.execute("SELECT *, EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as age FROM nodes ORDER BY hostname;")
            nodes = cur.fetchall()
            # In a real app, you'd calculate color, speed, etc. here
            for node in nodes:
                node['percent'] = node.get('progress', 0)
                node['color'] = 'primary'
                node['speed'] = '1.0'
                node['codec'] = 'hevc'

            # Fetch failure count
            cur.execute("SELECT COUNT(*) FROM transcode_history WHERE status = 'failed';")
            fail_count = cur.fetchone()['count']

            return jsonify({
                "nodes": nodes,
                "fail_count": fail_count,
                "db_error": None
            })
    except Exception as e:
        return jsonify({"db_error": str(e), "nodes": [], "fail_count": 0}), 500
    finally:
        put_db_conn(conn)

@app.route('/api/jobs')
def api_jobs():
    """Returns the current job queue."""
    conn = get_db_conn()
    if not conn:
        return jsonify({"db_error": "Database connection pool is not available."}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM job_queue ORDER BY created_at DESC;")
            jobs = cur.fetchall()
            return jsonify({"jobs": jobs, "db_error": None})
    except Exception as e:
        return jsonify({"db_error": str(e), "jobs": []}), 500
    finally:
        put_db_conn(conn)

# ==============================================================================
# Frontend Routes
# ==============================================================================

@app.route('/')
def index():
    """Renders the main dashboard page."""
    # For now, we pass no data, as the frontend will fetch it via API
    return render_template('index.html', settings={})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)