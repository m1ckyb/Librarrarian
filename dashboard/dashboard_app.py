import os
import sys
import time
import threading
import uuid
import base64
import json
from datetime import datetime
import logging
from plexapi.myplex import MyPlexAccount, MyPlexPinLogin
import subprocess
from flask import Flask, render_template, g, request, flash, redirect, url_for, jsonify, session

try:
    from plexapi.server import PlexServer
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from authlib.integrations.flask_client import OAuth
    from werkzeug.middleware.proxy_fix import ProxyFix
    import requests
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

# --- Custom Logging Filter ---
# This filter will suppress the noisy GET /api/scan/progress logs from appearing.
class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        # The log message for an access log is in record.args
        if record.args and len(record.args) >= 3 and isinstance(record.args[2], str):
            return '/api/scan/progress' not in record.args[2]
        return True

# Apply the filter to Werkzeug's logger (used by Flask's dev server and Gunicorn)
logging.getLogger('werkzeug').addFilter(HealthCheckFilter())

# If running behind a reverse proxy, this is crucial for url_for() to generate correct
# external URLs (e.g., for OIDC redirects).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Use the same DB config as the worker script
# It is recommended to use environment variables for sensitive data
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "192.168.10.120"),
    "user": os.environ.get("DB_USER", "transcode"),
    "password": os.environ.get("DB_PASSWORD"),
    "dbname": os.environ.get("DB_NAME", "codecshift")
}

def setup_auth(app):
    """Initializes and configures the authentication system."""
    app.config['AUTH_ENABLED'] = os.environ.get('AUTH_ENABLED', 'false').lower() == 'true'
    app.config['OIDC_ENABLED'] = os.environ.get('OIDC_ENABLED', 'false').lower() == 'true'
    app.config['LOCAL_LOGIN_ENABLED'] = os.environ.get('LOCAL_LOGIN_ENABLED', 'false').lower() == 'true'
    app.config['OIDC_PROVIDER_NAME'] = os.environ.get('OIDC_PROVIDER_NAME')

    if not app.config['AUTH_ENABLED']:
        return # Do nothing if auth is disabled

    # If auth is on, but no methods are enabled, disable auth to prevent a lockout.
    if not app.config['OIDC_ENABLED'] and not app.config['LOCAL_LOGIN_ENABLED']:
        print("⚠️ WARNING: AUTH_ENABLED is true, but no authentication methods are enabled. Disabling authentication.")
        app.config['AUTH_ENABLED'] = False
        return

    if app.config['OIDC_ENABLED']:
        oauth = OAuth(app)
        # Allow SSL verification to be disabled for development (e.g., with self-signed certs)
        ssl_verify = os.environ.get('OIDC_SSL_VERIFY', 'true').lower() == 'true'
        
        oauth.register(
            name='oidc_provider',
            client_id=os.environ.get('OIDC_CLIENT_ID'),
            client_secret=os.environ.get('OIDC_CLIENT_SECRET'),
            # Use a session that respects the SSL_VERIFY setting for fetching metadata
            fetch_token=lambda: oauth.fetch_access_token(verify=ssl_verify),
            server_metadata_url=f"{os.environ.get('OIDC_ISSUER_URL')}/.well-known/openid-configuration",
            client_kwargs={'scope': 'openid email profile'},
            # Explicitly define the supported signing algorithms for the ID token.
            # Authlib defaults to just 'RS256', but many providers use others.
            server_metadata_options={
                "id_token_signing_alg_values_supported": ["RS256", "RS384", "RS512",
                                                          "ES256", "ES384", "ES512"]
            }
        )
        app.oauth = oauth

    @app.before_request
    def require_login():
        """Protects all routes by requiring login if authentication is enabled."""
        if not app.config.get('AUTH_ENABLED'):
            return

        # If the user is logged in, allow access.
        if 'user' in session or request.path.startswith('/static') or request.endpoint in ['login', 'logout', 'authorize', 'login_oidc']:
            return

        # Block all unauthenticated API access.
        # This is for machine-to-machine communication (workers).
        if request.path.startswith('/api/'):
            api_key = request.headers.get('X-API-Key')
            if api_key and api_key == os.environ.get('API_KEY'):
                return # API key is valid, allow access
            return jsonify(error="Authentication required. Invalid or missing API Key."), 401
            return

        return redirect(url_for('login'))

    @app.context_processor
    def inject_auth_status():
        """Makes auth status available to all templates."""
        greeting = "Welcome"
        user_name = None
        if 'user' in session:
            # Determine a dynamic greeting based on the time of day.
            current_hour = datetime.now().hour
            if 5 <= current_hour < 12:
                greeting = "Good morning"
            elif 12 <= current_hour < 18:
                greeting = "Good afternoon"
            else:
                greeting = "Good evening"

            # OIDC providers might use 'name', 'email', or 'preferred_username'.
            user_info = session['user']
            user_name = user_info.get('name') or user_info.get('email') or user_info.get('preferred_username')
        return dict(
            auth_enabled=app.config.get('AUTH_ENABLED', False), 
            user_name=user_name, 
            greeting=greeting,
            oidc_provider_name=app.config.get('OIDC_PROVIDER_NAME'),
            version=get_project_version()
        )

# Initialize authentication
setup_auth(app)

def get_project_version():
    """Reads the version from the root VERSION.txt file."""
    try:
        # The Dockerfile copies VERSION.txt to the workdir /app
        return open('VERSION.txt', 'r').read().strip()
    except FileNotFoundError:
        # Fallback for local development where CWD might be different
        try:
            version_file = os.path.join(os.path.dirname(__file__), '..', 'VERSION.txt')
            return open(version_file, 'r').read().strip()
        except FileNotFoundError:
            return "unknown"

# Print a startup banner to the logs
print(f"\nCodecShift Web Dashboard v{get_project_version()}\n")

# ===========================
# Database Migrations
# ===========================
TARGET_SCHEMA_VERSION = 6

MIGRATIONS = {
    # Version 2: Add uptime tracking
    2: [
        "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS connected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        # Backfill the connected_at for existing nodes to prevent them from showing "N/A" uptime.
        # We'll use their last_heartbeat as a reasonable approximation for when they connected.
        "UPDATE nodes SET connected_at = last_heartbeat WHERE connected_at IS NULL;"
    ],
    # Version 3: Add Plex path mapping toggle and internal scanner settings
    3: [
        "INSERT INTO worker_settings (setting_name, setting_value) VALUES ('plex_path_mapping_enabled', 'true') ON CONFLICT (setting_name) DO NOTHING;",
        "INSERT INTO worker_settings (setting_name, setting_value) VALUES ('media_scanner_type', 'plex') ON CONFLICT (setting_name) DO NOTHING;",
        "INSERT INTO worker_settings (setting_name, setting_value) VALUES ('internal_scan_paths', '') ON CONFLICT (setting_name) DO NOTHING;"
    ],
    # Version 4: Add table for user-defined media source types
    4: [
        """
        CREATE TABLE IF NOT EXISTS media_source_types (
            id SERIAL PRIMARY KEY,
            source_name VARCHAR(255) NOT NULL,
            scanner_type VARCHAR(50) NOT NULL, -- 'plex' or 'internal'
            media_type VARCHAR(50) NOT NULL, -- 'movie', 'show', 'music', 'other'
            UNIQUE(source_name, scanner_type)
        );
        """
    ],
    # Version 5: Add 'is_hidden' flag to media sources
    5: [
        "ALTER TABLE media_source_types ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT false;"
    ],
    # Version 6: Add metadata column for advanced job types like renaming
    6: [
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS metadata JSONB;"
    ],
}

def run_migrations():
    """Checks the current DB schema version and applies any necessary migrations."""
    print("Checking database schema version...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Check if the schema_version table exists. If not, this is a pre-migration database.
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'schema_version')")
        if not cur.fetchone()[0]:
            print("Schema version table not found. Assuming version 1.")
            current_version = 1
            cur.execute("CREATE TABLE schema_version (version INT PRIMARY KEY);")
            cur.execute("INSERT INTO schema_version (version) VALUES (1);")
            conn.commit()
        else:
            cur.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            res = cur.fetchone()
            current_version = res[0] if res else 1

        print(f"Current schema version: {current_version}. Target version: {TARGET_SCHEMA_VERSION}.")

        if current_version >= TARGET_SCHEMA_VERSION:
            print("Database schema is up to date.")
            cur.close()
            conn.close()
            return

        # Apply migrations in order
        for version in sorted(MIGRATIONS.keys()):
            if version > current_version:
                print(f"Applying migration for version {version}...")
                for statement in MIGRATIONS[version]:
                    print(f"  -> Executing: {statement[:80]}...")
                    cur.execute(statement)
                cur.execute("UPDATE schema_version SET version = %s", (version,))
                conn.commit()
                print(f"Successfully migrated to version {version}.")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ CRITICAL: Database migration failed: {e}")
        print("   The application cannot start. Please resolve the database issue and restart the container.")
        sys.exit(1)

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
    print("Running database initialisation...")
    if not conn:
        print("DB Init Error: Could not connect to database.")
        return

    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id SERIAL PRIMARY KEY,
                hostname VARCHAR(255) UNIQUE NOT NULL,
                status VARCHAR(50),
                last_heartbeat TIMESTAMP,
                connected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                version VARCHAR(50),
                version_mismatch BOOLEAN DEFAULT false,
                command VARCHAR(50) DEFAULT 'idle',
                progress REAL,
                fps REAL,
                current_file TEXT
            );
        """)
        cur.execute("GRANT ALL PRIVILEGES ON TABLE nodes TO transcode;")
        cur.execute("GRANT USAGE, SELECT ON SEQUENCE nodes_id_seq TO transcode;")
        cur.execute("ALTER TABLE nodes OWNER TO transcode;")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                filepath TEXT NOT NULL UNIQUE,
                job_type VARCHAR(20) NOT NULL DEFAULT 'transcode',
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                assigned_to VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                metadata JSONB
            );
        """)
        cur.execute("GRANT ALL PRIVILEGES ON TABLE jobs TO transcode;")
        cur.execute("GRANT USAGE, SELECT ON SEQUENCE jobs_id_seq TO transcode;")
        cur.execute("ALTER TABLE jobs OWNER TO transcode;")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS worker_settings (
                id SERIAL PRIMARY KEY,
                setting_name VARCHAR(255) UNIQUE NOT NULL,
                setting_value TEXT
            );
        """)
        cur.execute("GRANT ALL PRIVILEGES ON TABLE worker_settings TO transcode;")
        cur.execute("GRANT USAGE, SELECT ON SEQUENCE worker_settings_id_seq TO transcode;")
        cur.execute("ALTER TABLE worker_settings OWNER TO transcode;")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS encoded_files (
                id SERIAL PRIMARY KEY,
                job_id INTEGER,
                filename TEXT,
                original_size BIGINT,
                new_size BIGINT,
                encoded_by TEXT,
                encoded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20)
            );
        """)
        cur.execute("GRANT ALL PRIVILEGES ON TABLE encoded_files TO transcode;")
        cur.execute("GRANT USAGE, SELECT ON SEQUENCE encoded_files_id_seq TO transcode;")
        cur.execute("ALTER TABLE encoded_files OWNER TO transcode;")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS failed_files (
                id SERIAL PRIMARY KEY,
                filename TEXT,
                reason TEXT,
                log TEXT,
                failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("GRANT ALL PRIVILEGES ON TABLE failed_files TO transcode;")
        cur.execute("GRANT USAGE, SELECT ON SEQUENCE failed_files_id_seq TO transcode;")
        cur.execute("ALTER TABLE failed_files OWNER TO transcode;")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS media_source_types (
                id SERIAL PRIMARY KEY,
                source_name VARCHAR(255) NOT NULL,
                scanner_type VARCHAR(50) NOT NULL,
                media_type VARCHAR(50) NOT NULL,
                is_hidden BOOLEAN DEFAULT false,
                UNIQUE(source_name, scanner_type)
            );
        """)
        cur.execute("GRANT ALL PRIVILEGES ON TABLE media_source_types TO transcode;")
        cur.execute("GRANT USAGE, SELECT ON SEQUENCE media_source_types_id_seq TO transcode;")
        cur.execute("ALTER TABLE media_source_types OWNER TO transcode;")

        cur.execute("""
            INSERT INTO worker_settings (setting_name, setting_value) VALUES
                ('rescan_delay_minutes', '0'),
                ('worker_poll_interval', '30'),
                ('min_length', '0.5'),
                ('backup_directory', ''),
                ('hardware_acceleration', 'auto'),
                ('keep_original', 'false'),
                ('allow_hevc', 'false'),
                ('allow_av1', 'false'),
                ('auto_update', 'false'),
                ('clean_failures', 'false'),
                ('debug', 'false'),
                ('plex_url', ''),
                ('plex_token', ''),
                ('plex_libraries', ''),
                ('nvenc_cq_hd', '32'),
                ('nvenc_cq_sd', '28'),
                ('vaapi_cq_hd', '28'),
                ('vaapi_cq_sd', '24'),
                ('cpu_cq_hd', '28'),
                ('cpu_cq_sd', '24'),
                ('cq_width_threshold', '1900'),
                ('plex_path_from', ''),
                ('plex_path_to', ''),
                ('pause_job_distribution', 'false'),
                ('plex_path_mapping_enabled', 'true'),
                ('media_scanner_type', 'plex'),
                ('internal_scan_paths', ''),
                ('sonarr_enabled', 'false'),
                ('radarr_enabled', 'false'),
                ('lidarr_enabled', 'false')
            ON CONFLICT (setting_name) DO NOTHING;
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INT PRIMARY KEY
            );
        """)
        cur.execute("ALTER TABLE schema_version OWNER TO transcode;")

    conn.commit()

def initialize_database_if_needed():
    """
    Checks if the database is initialized. If not, runs the full init_db() process.
    This prevents re-running all CREATE TABLE statements on every startup.
    """
    conn = None
    try:
        # Use a direct connection to check for initialization before the app context is fully ready.
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            # Check if a key table (like schema_version) exists.
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'schema_version')")
            table_exists = cur.fetchone()[0]
            
            if not table_exists:
                print("First run detected: Database not initialized. Running initial setup...")
                # We need an app context to call init_db()
                with app.app_context():
                    init_db()
            else:
                print("Database already initialized. Skipping initial setup.")
    except Exception as e:
        print(f"❌ CRITICAL: Could not connect to or initialize the database: {e}")
        sys.exit(1)

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
            # Also calculate the uptime based on the connected_at timestamp
            cur.execute("""
                SELECT 
                    *, 
                    EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as age, 
                    version_mismatch,
                    (NOW() - connected_at) as uptime
                FROM nodes
                WHERE last_heartbeat > NOW() - INTERVAL '5 minutes'
                ORDER BY hostname
            """)
            nodes = cur.fetchall()

            # Format uptime into a human-readable string
            for node in nodes:
                uptime_delta = node.get('uptime')
                if uptime_delta:
                    days = uptime_delta.days
                    hours, rem = divmod(uptime_delta.seconds, 3600)
                    minutes, _ = divmod(rem, 60)
                    node['uptime_str'] = f"{days}d {hours}h {minutes}m"
                else:
                    node['uptime_str'] = "N/A"
                # Remove the raw timedelta object as it's not JSON serializable
                node.pop('uptime', None)
            
            # Get total failure count
            cur.execute("SELECT COUNT(*) as cnt FROM failed_files")
            failures = cur.fetchone()['cnt']
    except Exception as e:
        db_error = f"Database query failed: {e}"

    # --- Server-Side Version Mismatch Check ---
    # The dashboard should be the source of truth for version mismatches.
    # This ensures that if the dashboard is updated, it will flag old workers.
    dashboard_version = get_project_version()
    if db is not None and dashboard_version != "unknown":
        with db.cursor() as cur:
            for node in nodes:
                is_mismatched = node['version'] != dashboard_version
                if node['version_mismatch'] != is_mismatched:
                    cur.execute("UPDATE nodes SET version_mismatch = %s WHERE hostname = %s", (is_mismatched, node['hostname']))
                    node['version_mismatch'] = is_mismatched # Update the live data
        db.commit()

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
                    -- The connected_at column will be set to its default value (CURRENT_TIMESTAMP)
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
            cur.execute("""
                SELECT *, encoded_by as hostname 
                FROM encoded_files ORDER BY encoded_at DESC LIMIT 100
            """)
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
        else:
            node['color'] = 'warning'
        
        # Add the 'percent' key that the template expects, defaulting to 0 if 'progress' is null
        if 'progress' in node:
            node['percent'] = int(node['progress'] or 0)
        
        # Re-implement Speed and Codec for the UI
        node['speed'] = round(node.get('fps', 0) / 24, 1) if node.get('fps') else 0.0
        node['codec'] = 'hevc'

    return render_template(
        'index.html', 
        nodes=nodes, 
        fail_count=fail_count, 
        db_error=db_error or settings_db_error, # Show error from either query
        settings=settings
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login for both OIDC and the local fallback mechanism."""
    if not app.config.get('AUTH_ENABLED'):
        return "Authentication is not enabled.", 404

    if request.method == 'POST':
        if not app.config.get('LOCAL_LOGIN_ENABLED'):
            return "Local login is disabled.", 403

        username = request.form.get('username')
        password = request.form.get('password')
        local_user = os.environ.get('LOCAL_USER')
        encoded_pass = os.environ.get('LOCAL_PASSWORD')
        local_pass = None

        try:
            if encoded_pass:
                local_pass = base64.b64decode(encoded_pass).decode('utf-8')
        except (base64.binascii.Error, UnicodeDecodeError):
            print("⚠️ WARNING: LOCAL_PASSWORD is not a valid base64 string.")
            flash('Server configuration error for local login.', 'danger')
            return redirect(url_for('login'))

        if local_user and local_pass and username == local_user and password == local_pass:
            session['user'] = {'email': local_user, 'name': 'Local Admin'}
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.', 'danger')
            return redirect(url_for('login')) # Redirect back on failure

    # For GET requests, just render the login page.
    return render_template('login.html', oidc_enabled=app.config.get('OIDC_ENABLED'), local_login_enabled=app.config.get('LOCAL_LOGIN_ENABLED'))

@app.route('/login/oidc')
def login_oidc():
    """Redirects the user to the OIDC provider to start the login flow."""
    if app.config.get('OIDC_ENABLED'):
        redirect_uri = url_for('authorize', _external=True)
        if hasattr(app, 'oauth') and 'oidc_provider' in app.oauth._clients:
            return app.oauth.oidc_provider.authorize_redirect(redirect_uri)
    return "OIDC is not enabled or configured.", 404

@app.route('/authorize')
def authorize():
    """Callback route for the OIDC provider."""
    if not hasattr(app, 'oauth') or 'oidc_provider' not in app.oauth._clients:
        return "OIDC provider not configured.", 500
    token = app.oauth.oidc_provider.authorize_access_token()
    session['user'] = token.get('userinfo')
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    """Logs the user out."""
    session.pop('user', None)
    if app.config.get('OIDC_ENABLED') and hasattr(app, 'oauth'):
        return redirect(app.oauth.oidc_provider.server_metadata.get('end_session_endpoint'))
    return redirect(url_for('login'))

@app.route('/options', methods=['POST'])
def options():
    """
    Handles the form submission for worker settings from the main dashboard.
    This route now follows the Post-Redirect-Get pattern and uses a single
    atomic transaction to save all settings.
    """
    settings_to_update = {
        'media_scanner_type': request.form.get('media_scanner_type', 'plex'),
        'rescan_delay_minutes': request.form.get('rescan_delay_minutes', '0'),
        'worker_poll_interval': request.form.get('worker_poll_interval', '30'),
        'min_length': request.form.get('min_length', '0.5'),
        'backup_directory': request.form.get('backup_directory', ''),
        'hardware_acceleration': request.form.get('hardware_acceleration', 'auto'),
        'keep_original': 'true' if 'keep_original' in request.form else 'false',
        'allow_hevc': 'true' if 'allow_hevc' in request.form else 'false',
        'allow_av1': 'true' if 'allow_av1' in request.form else 'false',
        'auto_update': 'true' if 'auto_update' in request.form else 'false',
        'clean_failures': 'true' if 'clean_failures' in request.form else 'false',
        'debug': 'true' if 'debug' in request.form else 'false',
        'plex_url': request.form.get('plex_url', ''),
        'nvenc_cq_hd': request.form.get('nvenc_cq_hd', '32'),
        'nvenc_cq_sd': request.form.get('nvenc_cq_sd', '28'),
        'vaapi_cq_hd': request.form.get('vaapi_cq_hd', '28'),
        'vaapi_cq_sd': request.form.get('vaapi_cq_sd', '24'),
        'cpu_cq_hd': request.form.get('cpu_cq_hd', '28'),
        'cpu_cq_sd': request.form.get('cpu_cq_sd', '24'),
        'cq_width_threshold': request.form.get('cq_width_threshold', '1900'),
        'plex_path_from': request.form.get('plex_path_from', ''),
        'plex_path_to': request.form.get('plex_path_to', ''),
        'plex_path_mapping_enabled': 'true' if 'plex_path_mapping_enabled' in request.form else 'false',
        'sonarr_enabled': 'true' if 'sonarr_enabled' in request.form else 'false',
        'radarr_enabled': 'true' if 'radarr_enabled' in request.form else 'false',
        'lidarr_enabled': 'true' if 'lidarr_enabled' in request.form else 'false',
    }
    # Add the new *Arr settings
    for arr_type in ['sonarr', 'radarr', 'lidarr']:
        settings_to_update[f'{arr_type}_host'] = request.form.get(f'{arr_type}_host', '')
        # Only update the API key if a new value is provided to avoid overwriting with blanks on password fields
        if request.form.get(f'{arr_type}_api_key'):
            settings_to_update[f'{arr_type}_api_key'] = request.form.get(f'{arr_type}_api_key')
    settings_to_update['sonarr_send_to_queue'] = 'true' if 'sonarr_send_to_queue' in request.form else 'false'
    # Convert hours from the form back to minutes for storage
    settings_to_update['sonarr_rescan_minutes'] = str(int(request.form.get('sonarr_rescan_hours', '1')) * 60)
    settings_to_update['sonarr_auto_scan_enabled'] = 'true' if 'sonarr_auto_scan_enabled' in request.form else 'false'
    plex_libraries = request.form.getlist('plex_libraries')
    settings_to_update['plex_libraries'] = ','.join(plex_libraries)
    internal_paths = request.form.getlist('internal_scan_paths')
    settings_to_update['internal_scan_paths'] = ','.join(internal_paths)

    db = get_db()
    if not db:
        flash('Could not connect to the database.', 'danger')
        return redirect(url_for('dashboard', _anchor='options-tab-pane'))

    try:
        with db.cursor() as cur:
            # 1. Update general worker settings
            for key, value in settings_to_update.items():
                cur.execute("""
                    INSERT INTO worker_settings (setting_name, setting_value) VALUES (%s, %s)
                    ON CONFLICT (setting_name) DO UPDATE SET setting_value = EXCLUDED.setting_value;
                """, (key, value))

            # 2. Update media type and hide status assignments
            all_plex_sources = {k.replace('type_plex_', '') for k in request.form if k.startswith('type_plex_')}
            all_internal_sources = {k.replace('type_internal_', '') for k in request.form if k.startswith('type_internal_')}

            for source_name in all_plex_sources:
                media_type = request.form.get(f'type_plex_{source_name}')
                is_hidden = (media_type == 'none')
                cur.execute("""
                    INSERT INTO media_source_types (source_name, scanner_type, media_type, is_hidden)
                    VALUES (%s, 'plex', %s, %s)
                    ON CONFLICT (source_name, scanner_type) DO UPDATE SET media_type = EXCLUDED.media_type, is_hidden = EXCLUDED.is_hidden;
                """, (source_name, media_type, is_hidden))

            for source_name in all_internal_sources:
                media_type = request.form.get(f'type_internal_{source_name}')
                is_hidden = (media_type == 'none')
                cur.execute("""
                    INSERT INTO media_source_types (source_name, scanner_type, media_type, is_hidden)
                    VALUES (%s, 'internal', %s, %s)
                    ON CONFLICT (source_name, scanner_type) DO UPDATE SET media_type = EXCLUDED.media_type, is_hidden = EXCLUDED.is_hidden;
                """, (source_name, media_type, is_hidden))

        db.commit()
        flash('Worker settings have been updated successfully!', 'success')

    except Exception as e:
        db.rollback()
        flash(f'Failed to update settings due to a database error: {e}', 'danger')

    return redirect(url_for('dashboard', _anchor='options-tab-pane'))

@app.route('/api/settings', methods=['GET'])
def api_settings():
    """Returns all worker settings as JSON."""
    settings, db_error = get_worker_settings()
    if db_error:
        return jsonify(settings={}, error=db_error), 500
    return jsonify(settings=settings, dashboard_version=get_project_version())

@app.route('/api/jobs/clear', methods=['POST'])
def api_clear_jobs():
    """Clears all 'pending' jobs from the job_queue table."""
    try:
        db = get_db()
        with db.cursor() as cur:
            # Use DELETE instead of TRUNCATE to preserve the ID sequence and avoid deleting active jobs.
            cur.execute("DELETE FROM jobs WHERE status = 'pending';")
        db.commit()
        return jsonify(success=True, message="Job queue cleared successfully.")
    except Exception as e:
        print(f"Error clearing job queue: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/jobs/delete/<int:job_id>', methods=['POST'])
def api_delete_job(job_id):
    """Deletes a single job from the jobs table."""
    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        db.commit()
        if cur.rowcount == 0:
            return jsonify(success=False, error="Job not found."), 404
        return jsonify(success=True, message=f"Job {job_id} deleted successfully.")
    except Exception as e:
        print(f"Error deleting job {job_id}: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/jobs', methods=['GET'])
def api_jobs():
    """Returns a paginated list of the current job queue as JSON."""
    db = get_db()
    jobs = []
    db_error = None
    total_jobs = 0
    page = request.args.get('page', 1, type=int)
    per_page = 50 # Number of jobs per page
    offset = (page - 1) * per_page

    if db is None:
        db_error = "Cannot connect to the PostgreSQL database."
        return jsonify(jobs=jobs, db_error=db_error, total_jobs=0, page=page, per_page=per_page)

    try:
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            # Query for the paginated list of jobs
            # This custom sort order brings 'encoding' jobs to the top, followed by 'pending'.
            # We also calculate the age of the job in minutes to detect stuck jobs.
            cur.execute("""
                SELECT *,
                       EXTRACT(EPOCH FROM (NOW() - updated_at)) / 60 AS age_minutes
                FROM jobs
                ORDER BY
                    CASE status
                        WHEN 'encoding' THEN 1
                        WHEN 'pending' THEN 2
                        WHEN 'failed' THEN 3
                        ELSE 4
                    END,
                    created_at DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))
            jobs = cur.fetchall()
            for job in jobs:
                job['created_at'] = job['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            
            # Query for the total number of jobs to calculate total pages
            cur.execute("SELECT COUNT(*) FROM jobs")
            total_jobs = cur.fetchone()['count']

    except Exception as e:
        db_error = f"Database query failed: {e}"

    return jsonify(jobs=jobs, db_error=db_error, total_jobs=total_jobs, page=page, per_page=per_page)

@app.route('/api/status')
def api_status():
    """Returns cluster status data as JSON."""
    nodes, fail_count, db_error = get_cluster_status()
    settings, _ = get_worker_settings()
    
    # Add the color key for the frontend to use
    for node in nodes:
        # Simplified color logic based on status
        if node.get('status') == 'encoding':
            node['color'] = 'success'
        elif node.get('status') == 'idle':
            node['color'] = 'secondary'
        else:
            node['color'] = 'warning'
        
        # Also add the 'percent' key for the client-side rendering
        node['percent'] = int(node.get('progress') or 0)

        # Re-implement Speed and Codec for the UI
        node['speed'] = round(node.get('fps', 0) / 24, 1) if node.get('fps') else 0.0
        node['codec'] = 'hevc'

    return jsonify(
        nodes=nodes,
        fail_count=fail_count,
        db_error=db_error,
        queue_paused=settings.get('pause_job_distribution', {}).get('setting_value') == 'true',
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
    history, db_error = get_history() # get_history is defined elsewhere
    for item in history:
        # Format datetime and sizes for display
        item['encoded_at'] = item['encoded_at'].strftime('%Y-%m-%d %H:%M:%S')
        item['original_size_gb'] = round(item['original_size'] / (1024**3), 2)
        item['new_size_gb'] = round(item['new_size'] / (1024**3), 2)
        item['reduction_percent'] = round((1 - item['new_size'] / item['original_size']) * 100, 1) if item['original_size'] > 0 else 0
        item['codec'] = 'hevc' # Add the missing codec key
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
            # Alias encoded_by to hostname to match the frontend template
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
            cur.execute("""
                SELECT *, encoded_by as hostname 
                FROM encoded_files WHERE status = 'completed' ORDER BY encoded_at DESC LIMIT 100
            """)
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
            item['codec'] = 'hevc' # Add the missing codec key

    except Exception as e:
        db_error = f"Database query failed: {e}"

    return jsonify(stats=stats, history=history, db_error=db_error)

@app.route('/api/jobs/create_cleanup', methods=['POST'])
def create_cleanup_jobs():
    """Triggers the background thread to scan for stale files."""
    if cleanup_scanner_lock.locked():
        return jsonify({"success": False, "message": "A cleanup scan is already in progress."})
    
    print(f"[{datetime.now()}] Manual cleanup scan requested via API.")
    
    # Trigger the background thread to run the scan
    cleanup_scan_now_event.set()
    return jsonify(success=True, message="Cleanup scan has been triggered. Check logs for progress.")

@app.route('/api/plex/login', methods=['POST'])
def plex_login():
    """Logs into Plex using username/password and saves the auth token."""
    username = request.json.get('username')
    password = request.json.get('password')
    plex_url = request.json.get('plex_url')

    if not username or not password:
        return jsonify(success=False, error="Username and password are required."), 400
    
    if not plex_url:
        return jsonify(success=False, error="Plex Server URL is required."), 400

    try:
        # Instantiate the account object with username and password to sign in.
        account = MyPlexAccount(username, password)
        token = account.authenticationToken
        if token:
            # Save both the URL and the token
            update_worker_setting('plex_url', plex_url)
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
    """Fetches a list of libraries from the configured Plex server, merged with saved settings."""
    settings, db_error = get_worker_settings()
    if db_error: return jsonify(libraries=[], error=db_error), 500

    plex_url = settings.get('plex_url', {}).get('setting_value')
    plex_token = settings.get('plex_token', {}).get('setting_value')

    if not all([plex_url, plex_token]):
        return jsonify(libraries=[], error="Plex is not configured or authenticated."), 400

    try:
        plex = PlexServer(plex_url, plex_token)
        db = get_db()

        # 1. Fetch saved types from the database into a dictionary
        saved_types = {}
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT source_name, media_type, is_hidden FROM media_source_types WHERE scanner_type = 'plex'")
            for row in cur.fetchall():
                saved_types[row['source_name']] = {'type': row['media_type'], 'is_hidden': row['is_hidden']}

        # 2. Fetch libraries from Plex and merge with saved settings
        result_libraries = []
        plex_sections = [s for s in plex.library.sections() if s.type in ['movie', 'show', 'artist', 'photo']]
        
        for section in plex_sections:
            saved_setting = saved_types.get(section.title)
            if saved_setting:
                result_libraries.append({
                    'title': section.title,
                    'type': saved_setting['type'],
                    'is_hidden': saved_setting['is_hidden'],
                    'plex_type': section.type,
                    'key': section.key
                })
            else:
                # If not in our DB, use Plex's info and default to not hidden
                result_libraries.append({
                    'title': section.title,
                    'type': section.type, # Default to the type from Plex
                    'is_hidden': False,
                    'plex_type': section.type,
                    'key': section.key
                })

        return jsonify(libraries=result_libraries)
    except Exception as e:
        return jsonify(libraries=[], error=f"Could not connect to Plex or process libraries: {e}"), 500

@app.route('/api/internal/folders', methods=['GET'])
def api_internal_folders():
    """Lists the subdirectories inside the /media folder and infers their type."""
    def infer_type(folder_name):
        """Simple heuristic to guess the folder type. Now includes music."""
        name = folder_name.lower()
        if 'movie' in name or 'film' in name:
            return 'movie'
        if 'tv' in name or 'show' in name or 'series' in name:
            return 'show'
        if 'music' in name or 'audio' in name:
            return 'music'
        return 'other' # Generic fallback

    media_path = '/media'
    folders = []
    try:
        db = get_db()
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            folder_names = [item for item in os.listdir(media_path) if os.path.isdir(os.path.join(media_path, item))] if os.path.isdir(media_path) else []
            
            if not folder_names:
                return jsonify(folders=[])

            # This query now correctly joins and handles NULLs for internal folders.
            cur.execute("""
                SELECT s.name, COALESCE(mst.media_type, s.inferred_type) as type, COALESCE(mst.is_hidden, false) as is_hidden
                FROM (SELECT unnest(%(names)s) as name, unnest(%(types)s) as inferred_type) s
                LEFT JOIN media_source_types mst ON s.name = mst.source_name AND mst.scanner_type = 'internal'
            """, {
                'names': folder_names,
                'types': [infer_type(name) for name in folder_names]
            })
            folders = cur.fetchall()

        # Sort by name for consistent ordering
        return jsonify(folders=sorted(folders, key=lambda x: x['name']))
    except Exception as e:
        print(f"Error listing internal folders: {e}")
        return jsonify(folders=[], error=str(e)), 500

# --- New Background Scanner and Worker API ---

scanner_lock = threading.Lock()
scan_now_event = threading.Event()
sonarr_rename_scan_event = threading.Event()
sonarr_quality_scan_event = threading.Event()
scan_cancel_event = threading.Event()
cleanup_scanner_lock = threading.Lock()
cleanup_scan_now_event = threading.Event()

# --- Global state for scan progress ---
scan_progress_state = {
    "is_running": False, "current_step": "", "total_steps": 0, "progress": 0
}

def sonarr_background_thread():
    """Waits for triggers to run Sonarr scans (rename, quality, etc.)."""
    while True:
        # Wait for either event to be set. This is a simple polling mechanism.
        if sonarr_rename_scan_event.wait(timeout=1):
            print(f"[{datetime.now()}] Sonarr rename scan trigger received.")
            scan_cancel_event.clear() # Ensure cancel flag is down before starting
            with app.app_context():
                run_sonarr_rename_scan()
            sonarr_rename_scan_event.clear()

        if sonarr_quality_scan_event.wait(timeout=1):
            print(f"[{datetime.now()}] Sonarr quality scan trigger received.")
            scan_cancel_event.clear() # Ensure cancel flag is down before starting
            with app.app_context():
                run_sonarr_quality_scan()
            sonarr_quality_scan_event.clear()

        time.sleep(1) # Prevent a tight loop

def run_sonarr_rename_scan():
    """
    Handles Sonarr integration. Can either trigger Sonarr's API directly
    or add 'rename' jobs to the local queue for a worker to process.
    """
    with app.app_context():
        settings, db_error = get_worker_settings()
        if db_error: return {"success": False, "message": "Database not available."}

        if settings.get('sonarr_enabled', {}).get('setting_value') != 'true':
            return {"success": False, "message": "Sonarr integration is disabled in Options."}

        host = settings.get('sonarr_host', {}).get('setting_value')
        api_key = settings.get('sonarr_api_key', {}).get('setting_value')
        send_to_queue = settings.get('sonarr_send_to_queue', {}).get('setting_value') == 'true'

        if not host or not api_key:
            return {"success": False, "message": "Sonarr is not configured."}

        if not send_to_queue:
            return {"success": False, "message": "Rename scan was triggered, but 'Send Rename Jobs to Queue' is disabled in Options."}

        if scanner_lock.acquire(blocking=False):
            try:
                print(f"[{datetime.now()}] Sonarr Rename Scanner: Starting deep scan to find files to rename...")
                headers = {'X-Api-Key': api_key}
                base_url = host.rstrip('/')
                series_res = requests.get(f"{base_url}/api/v3/series", headers=headers, timeout=10, verify=False)
                series_res.raise_for_status()
                all_series = series_res.json()

                scan_progress_state.update({"is_running": True, "total_steps": len(all_series), "progress": 0})
                conn = get_db()
                cur = conn.cursor()
                new_jobs_found = 0

                for i, series in enumerate(all_series):
                    series_title = series.get('title', 'Unknown Series')
                    # print(f"  -> Rename Scan ({i+1}/{len(all_series)}): Analyzing {series_title}")
                    scan_progress_state.update({"current_step": f"Analyzing: {series_title}", "progress": i + 1})
                    
                    if scan_cancel_event.is_set():
                        print("Rename scan cancelled by user.")
                        scan_progress_state["current_step"] = "Scan cancelled by user."
                        return {"success": False, "message": "Scan cancelled."}

                    requests.post(f"{base_url}/api/v3/command", headers=headers, json={'name': 'RescanSeries', 'seriesId': series['id']}, timeout=10)
                    time.sleep(2) # Give Sonarr a moment to process before we query
                    rename_res = requests.get(f"{base_url}/api/v3/rename?seriesId={series['id']}", headers=headers, timeout=10)
                    for episode in rename_res.json():
                        filepath = episode.get('existingPath')
                        if filepath:
                            metadata = {'source': 'sonarr', 'seriesTitle': series['title'], 'seasonNumber': episode.get('seasonNumber'), 'episodeNumber': episode.get('episodeNumbers', [0])[0], 'episodeTitle': "Episode", 'quality': "N/A"}
                            cur.execute("INSERT INTO jobs (filepath, job_type, status, metadata) VALUES (%s, 'Rename Job', 'awaiting_approval', %s) ON CONFLICT (filepath) DO NOTHING", (filepath, json.dumps(metadata)))
                            if cur.rowcount > 0: new_jobs_found += 1
                
                conn.commit()
                message = f"Sonarr deep scan complete. Found {new_jobs_found} new files to rename."
                scan_progress_state["current_step"] = message
                return {"success": True, "message": message}
            except Exception as e:
                return {"success": False, "message": f"An error occurred during the deep scan: {e}"}
            finally:
                # Only reset progress if it wasn't a cancellation
                if not scan_cancel_event.is_set(): scan_progress_state.update({"current_step": "", "progress": 0})
                scan_progress_state["is_running"] = False
                if scanner_lock.locked(): scanner_lock.release()
        else:
            return {"success": False, "message": "Scan trigger ignored: Another scan is already in progress."}

def run_sonarr_deep_scan():
    """
    Performs a deep, slow scan of the entire Sonarr library. For each series,
    it triggers a rescan and then checks for files that need renaming.
    This is resource-intensive and should be used sparingly.
    """
    with app.app_context():
        settings, db_error = get_worker_settings()
        if db_error: return {"success": False, "message": "Database not available."}

        if settings.get('sonarr_enabled', {}).get('setting_value') != 'true':
            return {"success": False, "message": "Sonarr integration is disabled in Options."}

        host = settings.get('sonarr_host', {}).get('setting_value')
        api_key = settings.get('sonarr_api_key', {}).get('setting_value')

        if not host or not api_key:
            return {"success": False, "message": "Sonarr is not configured."}

        send_to_queue = settings.get('sonarr_send_to_queue', {}).get('setting_value') == 'true'
        if not send_to_queue:
            return {"success": False, "message": "Rename scan was triggered, but 'Send Rename Jobs to Queue' is disabled in Options."}

        if scanner_lock.acquire(blocking=False):
            try:
                headers = {'X-Api-Key': api_key}
                base_url = host.rstrip('/')
                series_res = requests.get(f"{base_url}/api/v3/series", headers=headers, timeout=10, verify=False)
                series_res.raise_for_status()
                all_series = series_res.json()

                scan_progress_state.update({"is_running": True, "total_steps": len(all_series), "progress": 0})
                conn = get_db()
                cur = conn.cursor()
                new_jobs_found = 0

                for i, series in enumerate(all_series):
                    series_title = series.get('title', 'Unknown Series')
                    print(f"  -> Rename Scan ({i+1}/{len(all_series)}): Analyzing {series_title}")
                    scan_progress_state.update({"current_step": f"Analyzing: {series_title}", "progress": i + 1})
                    
                    # This is the correct pattern: trigger a scan, then check for results.
                    requests.post(f"{base_url}/api/v3/command", headers=headers, json={'name': 'RescanSeries', 'seriesId': series['id']}, timeout=10, verify=False)
                    time.sleep(2) # Give Sonarr a moment to process before we query
                    rename_res = requests.get(f"{base_url}/api/v3/rename?seriesId={series['id']}", headers=headers, timeout=10, verify=False)
                    for episode in rename_res.json():
                        filepath = episode.get('existingPath')
                        if filepath:
                            metadata = {'source': 'sonarr', 'seriesTitle': series['title'], 'seasonNumber': episode.get('seasonNumber'), 'episodeNumber': episode.get('episodeNumbers', [0])[0], 'episodeTitle': "Episode", 'quality': "N/A"}
                            cur.execute("INSERT INTO jobs (filepath, job_type, status, metadata) VALUES (%s, 'Rename Job', 'awaiting_approval', %s) ON CONFLICT (filepath) DO NOTHING", (filepath, json.dumps(metadata)))
                            if cur.rowcount > 0: new_jobs_found += 1
                
                conn.commit()
                message = f"Sonarr deep scan complete. Found {new_jobs_found} new files to rename."
                scan_progress_state["current_step"] = message
                return {"success": True, "message": message}
            except Exception as e:
                return {"success": False, "message": f"An error occurred during the deep scan: {e}"}
            finally:
                scan_progress_state.update({"is_running": False, "current_step": "", "progress": 0})
                if scanner_lock.locked(): scanner_lock.release()
        else:
            # This case handles when the lock is already held.
            return {"success": False, "message": "Scan trigger ignored: Another scan is already in progress."}

def run_sonarr_quality_scan():
    """
    Scans Sonarr for quality mismatches. If a series has a quality profile
    with a cutoff higher than the quality of an individual episode file,
    a 'quality_mismatch' job is created for investigation.
    """
    with app.app_context():
        settings, db_error = get_worker_settings()
        if db_error: return {"success": False, "message": "Database not available."}

        host = settings.get('sonarr_host', {}).get('setting_value')
        api_key = settings.get('sonarr_api_key', {}).get('setting_value')

        if not host or not api_key:
            return {"success": False, "message": "Sonarr is not configured."}

        print(f"[{datetime.now()}] Sonarr Quality Scanner: Starting scan...")
        if not scanner_lock.acquire(blocking=False):
            return {"success": False, "message": "Scan trigger ignored: Another scan is already in progress."}

        try:
            headers = {'X-Api-Key': api_key}
            base_url = host.rstrip('/')

            # 1. Get all quality profiles to map IDs to names and cutoffs
            profiles_res = requests.get(f"{base_url}/api/v3/qualityprofile", headers=headers, timeout=10, verify=False)
            profiles_res.raise_for_status()
            quality_profiles = {p['id']: p for p in profiles_res.json()}

            # 2. Get all series
            series_res = requests.get(f"{base_url}/api/v3/series", headers=headers, timeout=10, verify=False)
            series_res.raise_for_status()
            all_series = series_res.json()

            # --- Progress Tracking ---
            total_series = len(all_series)
            scan_progress_state.update({"is_running": True, "total_steps": total_series, "progress": 0})

            conn = get_db()
            cur = conn.cursor()
            new_jobs_found = 0

            for i, series in enumerate(all_series):
                series_title = series.get('title', 'Unknown Series')
                # print(f"  -> ({i+1}/{total_series}) Checking series: {series_title}")
                scan_progress_state.update({"current_step": series_title, "progress": i + 1})

                if scan_cancel_event.is_set():
                    # This is the correct pattern: trigger a scan, then check for results.
                    # We add a small delay to give Sonarr time to update its internal state after the rescan command.
                    requests.post(f"{base_url}/api/v3/command", headers=headers, json={'name': 'RescanSeries', 'seriesId': series['id']}, timeout=10, verify=False)
                    time.sleep(2) # Give Sonarr a moment to process before we query
                    print("Quality scan cancelled by user.")
                    scan_progress_state["current_step"] = "Scan cancelled by user."
                    return {"success": False, "message": "Scan cancelled."}

                profile = quality_profiles.get(series['qualityProfileId'])
                if not profile or not profile.get('cutoff'):
                    continue # Skip series without a valid quality profile or cutoff

                # 3. Get all episodes for the series
                episodes_res = requests.get(f"{base_url}/api/v3/episode?seriesId={series['id']}", headers=headers, timeout=20, verify=False)
                episodes_res.raise_for_status()
                
                for episode in episodes_res.json():
                    if episode.get('hasFile') and episode.get('episodeFile', {}).get('qualityCutoffNotMet', False):
                        filepath = episode['episodeFile']['path']
                        metadata = {'source': 'sonarr', 'job_class': 'quality_mismatch', 'seriesTitle': series['title'], 'seasonNumber': episode['seasonNumber'], 'episodeNumber': episode['episodeNumber'], 'episodeTitle': episode['title'], 'file_quality': episode['episodeFile']['quality']['quality']['name'], 'profile_quality': profile['name']}
                        cur.execute("INSERT INTO jobs (filepath, job_type, status, metadata) VALUES (%s, 'Quality Mismatch', 'awaiting_approval', %s) ON CONFLICT (filepath) DO NOTHING", (filepath, json.dumps(metadata)))
                        if cur.rowcount > 0: new_jobs_found += 1
            
            conn.commit()
            message = f"Sonarr quality scan complete. Found {new_jobs_found} potential mismatches."
            scan_progress_state["current_step"] = message # Set final message
            return {"success": True, "message": message}
        except requests.RequestException as e:
            return {"success": False, "message": f"Could not connect to Sonarr: {e}"}
        finally:
            # Only reset progress if it wasn't a cancellation
            if not scan_cancel_event.is_set(): scan_progress_state.update({"current_step": "", "progress": 0})
            scan_progress_state["is_running"] = False
            if scanner_lock.locked(): scanner_lock.release()

def run_internal_scan(force_scan=False):
    """
    The core logic for scanning local directories.
    """
    with app.app_context():
        settings, db_error = get_worker_settings()
        if db_error:
            return {"success": False, "message": "Database not available."}

        scan_paths_str = settings.get('internal_scan_paths', {}).get('setting_value', '')
        scan_paths = [path.strip() for path in scan_paths_str.split(',') if path.strip()]

        if not scan_paths:
            return {"success": False, "message": "Internal scanner is enabled, but no paths are configured to be scanned."}

        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if force_scan:
            existing_jobs = set()
            encoded_history = set()
        else:
            cur.execute("SELECT filepath FROM jobs")
            existing_jobs = {row['filepath'] for row in cur.fetchall()}
            cur.execute("SELECT filename FROM encoded_files")
            encoded_history = {row['filename'] for row in cur.fetchall()}
        
        new_files_found = 0
        valid_extensions = ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm')
        print(f"[{datetime.now()}] Internal Scanner: Starting scan of paths: {', '.join(scan_paths)}")

        for folder in scan_paths:
            full_scan_path = os.path.join('/media', folder)
            print(f"[{datetime.now()}] Internal Scanner: Scanning '{full_scan_path}'...")
            for root, _, files in os.walk(full_scan_path):
                for file in files:
                    if not file.lower().endswith(valid_extensions):
                        continue
                    
                    filepath = os.path.join(root, file)
                    if filepath in existing_jobs or filepath in encoded_history:
                        continue

                    try:
                        # Use ffprobe to get the video codec
                        ffprobe_cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", filepath]
                        codec = subprocess.check_output(ffprobe_cmd, text=True).strip()
                        
                        print(f"  - Checking: {os.path.basename(filepath)} (Codec: {codec or 'N/A'})")
                        if codec and codec not in ['hevc', 'h265']:
                            print(f"    -> Found non-HEVC file. Adding to queue.")
                            cur.execute("INSERT INTO jobs (filepath, job_type, status) VALUES (%s, 'transcode', 'pending') ON CONFLICT (filepath) DO NOTHING", (filepath,))
                            if cur.rowcount > 0:
                                new_files_found += 1
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        print(f"    -> Could not probe file '{filepath}'. Error: {e}")

        conn.commit()
        message = f"Scan complete. Added {new_files_found} new transcode jobs." if new_files_found > 0 else "Scan complete. No new files to add."
        cur.close()
        return {"success": True, "message": message}

def run_plex_scan(force_scan=False):
    """
    The core logic for scanning Plex libraries. This function is designed to be
    called ONLY by the background scanner thread.
    It uses a lock to prevent concurrent scans.
    """
    if not scanner_lock.acquire(blocking=False):
        print(f"[{datetime.now()}] Scan trigger ignored: A scan is already in progress.")
        return {"success": False, "message": "Scan trigger ignored: A scan is already in progress."}

    try:
        with app.app_context():
            settings, db_error = get_worker_settings()

            if db_error:
                return {"success": False, "message": "Database not available."}

            plex_url = settings.get('plex_url', {}).get('setting_value')
            plex_token = settings.get('plex_token', {}).get('setting_value')
            plex_libraries_str = settings.get('plex_libraries', {}).get('setting_value', '')
            plex_libraries = [lib.strip() for lib in plex_libraries_str.split(',') if lib.strip()]

            if not all([plex_url, plex_token, plex_libraries]):
                return {"success": False, "message": "Plex integration is not fully configured."}

            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            try:
                plex_server = PlexServer(plex_url, plex_token)
            except Exception as e:
                return {"success": False, "message": f"Could not connect to Plex server: {e}"}

            # Only check existing jobs/history if it's NOT a forced scan
            if force_scan:
                existing_jobs = set()
                encoded_history = set()
            else:
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
                    # Must reload to get all media part and stream details
                    video.reload()
                    
                    # Use the primary media object's codec for simplicity and reliability
                    if not hasattr(video, 'media') or not video.media:
                        continue

                    codec = video.media[0].videoCodec
                    filepath = video.media[0].parts[0].file

                    print(f"  - Checking: {os.path.basename(filepath)} (Codec: {codec or 'N/A'})")
                    if codec and codec not in ['hevc', 'h265'] and filepath not in existing_jobs and filepath not in encoded_history:
                        print(f"    -> Found non-HEVC file. Adding to queue.")
                        cur.execute("INSERT INTO jobs (filepath, job_type, status) VALUES (%s, 'transcode', 'pending') ON CONFLICT (filepath) DO NOTHING", (filepath,))
                        if cur.rowcount > 0:
                            new_files_found += 1
            
            # Commit all the inserts at the end of the scan
            conn.commit()
            message = f"Scan complete. Added {new_files_found} new transcode jobs." if new_files_found > 0 else "Scan complete. No new files to add."
            cur.close()
            return {"success": True, "message": message}
    finally:
        scanner_lock.release()

@app.route('/api/scan/trigger', methods=['POST'])
def api_trigger_scan():
    """API endpoint to manually trigger a Plex scan."""
    if scanner_lock.locked():
        return jsonify({"success": False, "message": "A scan is already in progress."})
    
    force = request.json.get('force', False) if request.is_json else False
    print(f"[{datetime.now()}] Manual scan requested via API (Force: {force}).")
    
    # Trigger the background thread to run the scan with the correct force flag
    scan_now_event.set() 
    return jsonify({"success": True, "message": "Scan has been triggered. Check logs for progress."})

@app.route('/api/scan/rename', methods=['POST'])
def api_trigger_rename_scan():
    """API endpoint to manually trigger a Sonarr rename/import scan or add jobs to queue."""
    if scanner_lock.locked():
        return jsonify({"success": False, "message": "Another scan is already in progress."})
    sonarr_rename_scan_event.set()
    return jsonify(success=True, message="Sonarr rename scan has been triggered.")

@app.route('/api/scan/quality', methods=['POST'])
def api_trigger_quality_scan():
    """API endpoint to manually trigger a Sonarr quality mismatch scan."""
    if scanner_lock.locked():
        return jsonify({"success": False, "message": "Another scan is already in progress."})
    sonarr_quality_scan_event.set()
    return jsonify(success=True, message="Sonarr quality mismatch scan has been triggered.")

@app.route('/api/scan/cancel', methods=['POST'])
def api_cancel_scan():
    """API endpoint to signal cancellation of any active Sonarr scan."""
    print(f"[{datetime.now()}] Scan cancellation requested via API.")
    scan_cancel_event.set()
    return jsonify(success=True, message="Scan cancellation signal sent.")

@app.route('/api/scan/progress')
def api_scan_progress():
    """Returns the current progress of any active background scan."""
    return jsonify(scan_progress_state)

def run_cleanup_scan():
    """
    The core logic for scanning the media directory for stale files.
    This function is designed to be called ONLY by a background thread.
    """
    if not cleanup_scanner_lock.acquire(blocking=False):
        print(f"[{datetime.now()}] Cleanup scan trigger ignored: A scan is already in progress.")
        return

    try:
        with app.app_context():
            settings, _ = get_worker_settings()
            plex_url = settings.get('plex_url', {}).get('setting_value')
            plex_token = settings.get('plex_token', {}).get('setting_value')
            plex_libraries_str = settings.get('plex_libraries', {}).get('setting_value', '')
            plex_libraries = {lib.strip() for lib in plex_libraries_str.split(',') if lib.strip()}
            path_from = settings.get('plex_path_from', {}).get('setting_value')
            path_to = settings.get('plex_path_to', {}).get('setting_value')

            if not all([plex_url, plex_token, plex_libraries]):
                print(f"[{datetime.now()}] Cleanup scan skipped: Plex integration is not fully configured.")
                return

            # Get the root paths from the monitored Plex libraries
            scan_paths = set()
            try:
                plex = PlexServer(plex_url, plex_token)
                for section in plex.library.sections():
                    if section.title in plex_libraries:
                        for location in section.locations:
                            local_path = location
                            # Only perform path replacement if the feature is enabled
                            # and both 'from' and 'to' paths are actually defined.
                            path_mapping_enabled = settings.get('plex_path_mapping_enabled', {}).get('setting_value') == 'true'
                            if path_mapping_enabled and path_from and path_to:
                                local_path = location.replace(path_from, path_to, 1)
                                print(f"[{datetime.now()}] Cleanup Scanner: Mapping Plex path '{location}' to '{local_path}'")
                            else:
                                print(f"[{datetime.now()}] Cleanup Scanner: Using direct Plex path '{location}' (mapping disabled or not configured).")
                            scan_paths.add(local_path)
            except Exception as e:
                print(f"[{datetime.now()}] Cleanup scan failed: Could not connect to Plex to get library paths. Error: {e}")
                return

            if not scan_paths:
                print(f"[{datetime.now()}] Cleanup scan finished: No valid library paths found to scan.")
                return

            print(f"[{datetime.now()}] Cleanup Scanner: Starting scan of paths: {', '.join(scan_paths)}")
            jobs_created = 0
            db = get_db()
            with db.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT filepath FROM jobs")
                existing_jobs = {row['filepath'] for row in cur.fetchall()}

                for path in scan_paths:
                    if not os.path.isdir(path): continue
                    # Scan for files ending in .lock or starting with tmp_
                    for root, _, files in os.walk(path):
                        for file in files:
                            if file.endswith('.lock') or file.startswith('tmp_'):
                                full_path = os.path.join(root, file)
                                if full_path not in existing_jobs:
                                    cur.execute(
                                        "INSERT INTO jobs (filepath, job_type, status) VALUES (%s, 'cleanup', 'awaiting_approval')",
                                        (full_path,))
                                    jobs_created += 1
            db.commit()
            print(f"[{datetime.now()}] Cleanup scan complete. Created {jobs_created} cleanup jobs.")
    except Exception as e:
        print(f"[{datetime.now()}] Error during cleanup scan: {e}")
    finally:
        cleanup_scanner_lock.release()

@app.route('/api/jobs/release', methods=['POST'])
def release_cleanup_jobs():
    """Changes the status of cleanup jobs from 'awaiting_approval' to 'pending'."""
    data = request.get_json()
    job_ids = data.get('job_ids')
    release_all = data.get('release_all', False)

    try:
        db = get_db()
        with db.cursor() as cur:
            if release_all:
                cur.execute("UPDATE jobs SET status = 'pending' WHERE job_type = 'cleanup' AND status = 'awaiting_approval'")
            elif job_ids:
                # The '%s' placeholder will be correctly formatted by psycopg2 for the IN clause
                cur.execute("UPDATE jobs SET status = 'pending' WHERE id IN %s AND job_type = 'cleanup' AND status = 'awaiting_approval'", (tuple(job_ids),))
        db.commit()
        return jsonify(success=True, message="Selected cleanup jobs have been released to the queue.")
    except Exception as e:
        print(f"Error releasing cleanup jobs: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/arr/test', methods=['POST'])
def api_arr_test():
    """Tests the connection to a Sonarr/Radarr/Lidarr instance."""
    data = request.get_json()
    arr_type = data.get('arr_type')
    host = data.get('host')
    api_key = data.get('api_key')

    if not all([arr_type, host, api_key]):
        return jsonify(success=False, message="Missing required parameters."), 400

    # Use /api/v3/system/status for modern Sonarr/Radarr, /api/v1 for Lidarr
    api_version = 'v1' if arr_type == 'lidarr' else 'v3'
    test_url = f"{host.rstrip('/')}/api/{api_version}/system/status"
    headers = {'X-Api-Key': api_key}

    try:
        # Make the request with a timeout and without SSL verification for local setups
        response = requests.get(test_url, headers=headers, timeout=5, verify=False)

        if response.status_code == 200:
            # Check for a valid JSON response as an extra verification step
            response_data = response.json()
            if 'version' in response_data:
                return jsonify(success=True, message=f"Success! Connected to {arr_type.capitalize()} version {response_data['version']}.")
            else:
                return jsonify(success=False, message="Connection successful, but the response was not as expected.")
        else:
            return jsonify(success=False, message=f"Connection failed. Status code: {response.status_code}. Check URL and API Key."), 400
    except requests.exceptions.Timeout:
        return jsonify(success=False, message="Connection failed: The request timed out. Check the host address and port."), 500
    except requests.exceptions.RequestException as e:
        return jsonify(success=False, message=f"Connection failed: {e}. Check the host address and ensure it is reachable."), 500

@app.route('/api/queue/toggle_pause', methods=['POST'])
def toggle_pause_queue():
    """Toggles the paused state of the job queue."""
    settings, _ = get_worker_settings()
    current_state = settings.get('pause_job_distribution', {}).get('setting_value', 'false')
    new_state = 'false' if current_state == 'true' else 'true'
    success, error = update_worker_setting('pause_job_distribution', new_state)
    if success:
        return jsonify(success=True, new_state=new_state)
    else:
        return jsonify(success=False, error=error), 500

@app.route('/api/request_job', methods=['POST'])
def request_job():
    """Endpoint for workers to request a new job."""
    worker_hostname = request.json.get('hostname')
    if not worker_hostname:
        return jsonify({"error": "Hostname is required"}), 400
    
    print(f"[{datetime.now()}] Job request received from worker: {worker_hostname}")
    
    # Check if the queue is paused
    settings, _ = get_worker_settings()
    if settings.get('pause_job_distribution', {}).get('setting_value') == 'true':
        print(f"[{datetime.now()}] Job request from {worker_hostname} denied: Queue is paused.")
        return jsonify({}) # Return empty response as if no jobs are available

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("BEGIN;") # Start a transaction
        cur.execute("SELECT id, filepath, job_type FROM jobs WHERE status = 'pending' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED")
        job = cur.fetchone()

        if job:
            cur.execute("UPDATE jobs SET status = 'encoding', assigned_to = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (worker_hostname, job['id']))
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
                "INSERT INTO encoded_files (job_id, filename, original_size, new_size, encoded_by, status) VALUES (%s, %s, %s, %s, %s, 'completed')",
                (job_id, job['filepath'], data.get('original_size'), data.get('new_size'), job['assigned_to'])
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

        elif job['job_type'] == 'cleanup':
            # For cleanups, add a simplified entry to the history
            cur.execute(
                "INSERT INTO encoded_files (job_id, filename, original_size, new_size, encoded_by, status) VALUES (%s, %s, 0, 0, %s, 'completed')",
                (job_id, job['filepath'], job['assigned_to'])
            )
        # For all completed jobs (transcode or cleanup), delete from the jobs queue
        cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        message = f"Job {job_id} ({job['job_type']}) completed and removed from queue."

    elif status == 'failed':
        # For any failed job, log it and mark as failed in the queue
        cur.execute("INSERT INTO failed_files (filename, reason, log) VALUES (%s, %s, %s)", (job['filepath'], data.get('reason'), data.get('log')))
        cur.execute("INSERT INTO failed_files (filename, reason, log, reported_at) VALUES (%s, %s, %s, CURRENT_TIMESTAMP)", (job['filepath'], data.get('reason'), data.get('log')))
        cur.execute("UPDATE jobs SET status = 'failed', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (job_id,))
        message = f"Job {job_id} ({job['job_type']}) failed and logged."

    conn.commit()
    cur.close()
    return jsonify({"message": message})


# --- Background Threads ---

def plex_scanner_thread():
    """Scans Plex libraries and adds non-HEVC files to the jobs table."""
    while True:
        print(f"[{datetime.now()}] Automatic scanner is waiting for the next cycle.")
        # Use the rescan delay from settings, default to 0 (disabled)
        delay = 0 
        try:
            with app.app_context():
                settings, _ = get_worker_settings()
                delay_str = settings.get('rescan_delay_minutes', {}).get('setting_value', '0')
                delay = int(float(delay_str) * 60)
        except Exception as e:
            print(f"[{datetime.now()}] Could not get rescan delay from settings, defaulting to disabled. Error: {e}")
        
        # If delay is 0, wait indefinitely until a manual scan is triggered.
        # Otherwise, wait for the specified delay.
        wait_timeout = None if delay <= 0 else delay
        scan_triggered = scan_now_event.wait(timeout=wait_timeout)
        
        if scan_triggered:
            print(f"[{datetime.now()}] Manual scan trigger received.")
            with app.app_context():
                settings, _ = get_worker_settings()
                scanner_type = settings.get('media_scanner_type', {}).get('setting_value', 'plex')
                if scanner_type == 'internal':
                    run_internal_scan(force_scan=True)
                else:
                    run_plex_scan(force_scan=True)
            scan_now_event.clear() # Reset the event for the next time
        elif delay > 0:
            print(f"[{datetime.now()}] Rescan delay finished. Triggering automatic Plex scan.")
            # This will need to be updated to also check scanner type
            run_plex_scan(force_scan=False)

def cleanup_scanner_thread():
    """Waits for a trigger to scan for stale files."""
    while True:
        # Wait indefinitely until the event is set
        cleanup_scan_now_event.wait()
        print(f"[{datetime.now()}] Manual cleanup scan trigger received.")
        cleanup_scan_now_event.clear() # Reset the event
        run_cleanup_scan()

# Start the background threads when the app is initialized by Gunicorn.
scanner_thread = threading.Thread(target=plex_scanner_thread, daemon=True)
scanner_thread.start()
sonarr_background_scanner = threading.Thread(target=sonarr_background_thread, daemon=True)
sonarr_background_scanner.start()
cleanup_thread = threading.Thread(target=cleanup_scanner_thread, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    # Run migrations before starting the Flask app for local development
    initialize_database_if_needed()
    run_migrations()
    # Use host='0.0.0.0' to make the app accessible on your network
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # When run by Gunicorn in production, run migrations first
    initialize_database_if_needed()
    run_migrations()