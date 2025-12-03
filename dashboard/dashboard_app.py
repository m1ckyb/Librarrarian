import os
import sys
import time
import threading
import uuid
import base64
import json
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
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
    # This part is for user feedback when running locally without installing requirements
    print("❌ Error: Missing required packages for the web dashboard.")
    print("   Please run: pip install Flask psycopg2-binary")
    sys.exit(1)
# ===========================
# Configuration
# ===========================
app = Flask(__name__)

# --- Thread Synchronization Event ---
db_ready_event = threading.Event() # This will be set after migrations are complete

# A secret key is required for session management (e.g., for flash messages)
# It's recommended to set this as an environment variable in production.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a-super-secret-key-for-dev")


# --- Custom Logging Filter ---
# This filter will suppress noisy polling endpoints from appearing in the logs.
class HealthCheckFilter(logging.Filter):
    # Endpoints to suppress from logs (these are polled frequently by the UI)
    SUPPRESSED_ENDPOINTS = ['/api/scan/progress', '/api/status', '/api/health']

    def filter(self, record):
        # The log message for an access log is in record.args
        if record.args and len(record.args) >= 3 and isinstance(record.args[2], str):
            log_path = record.args[2]
            return not any(endpoint in log_path for endpoint in self.SUPPRESSED_ENDPOINTS)
        return True

# Apply the filter to Werkzeug's logger (used by Flask's dev server and Gunicorn)
logging.getLogger('werkzeug').addFilter(HealthCheckFilter())
# Also apply to Gunicorn's access logger
logging.getLogger('gunicorn.access').addFilter(HealthCheckFilter())

# If running behind a reverse proxy, this is crucial for url_for() to generate correct
# external URLs (e.g., for OIDC redirects).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# --- Security Headers ---
@app.after_request
def set_security_headers(response):
    """
    Adds security headers to all responses to protect against common web vulnerabilities.
    """
    # Prevent clickjacking attacks by disallowing the page to be displayed in a frame
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # Enable XSS protection in older browsers (modern browsers use CSP instead)
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Referrer policy to control how much referrer information is shared
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Permissions policy to restrict access to browser features
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response

# Use the same DB config as the worker script
# It is recommended to use environment variables for sensitive data
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "192.168.10.120"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "user": os.environ.get("DB_USER", "librarrarian"),
    "password": os.environ.get("DB_PASSWORD"),
    "dbname": os.environ.get("DB_NAME", "librarrarian")
}

# Worker session configuration
WORKER_SESSION_TIMEOUT_SECONDS = 300  # 5 minutes - time before a worker is considered stale
WORKER_PROTECTED_ENDPOINTS = ['request_job', 'update_job']  # Endpoints that require session validation

def setup_auth(app):
    """Initializes and configures the authentication system."""
    app.config['AUTH_ENABLED'] = os.environ.get('AUTH_ENABLED', 'false').lower() == 'true'
    app.config['OIDC_ENABLED'] = os.environ.get('OIDC_ENABLED', 'false').lower() == 'true'
    app.config['LOCAL_LOGIN_ENABLED'] = os.environ.get('LOCAL_LOGIN_ENABLED', 'false').lower() == 'true'
    app.config['OIDC_PROVIDER_NAME'] = os.environ.get('OIDC_PROVIDER_NAME')
    app.config['DEVMODE'] = os.environ.get('DEVMODE', 'false').lower() == 'true'

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
        # --- Dev Mode Bypass ---
        # If dev mode is on, bypass authentication for local network requests.
        if app.config.get('DEVMODE'):
            remote_ip = request.remote_addr
            if remote_ip and (remote_ip == '127.0.0.1' or remote_ip.startswith('192.168.') or remote_ip.startswith('172.')):
                # In dev mode, we can create a dummy session for a better UI experience
                if 'user' not in session:
                    session['user'] = {'name': 'Dev User'}
                return # Bypass further auth checks
        if not app.config.get('AUTH_ENABLED'):
            return

        # If the user is logged in, allow access.
        if 'user' in session or request.path.startswith('/static') or request.endpoint in ['login', 'logout', 'authorize', 'login_oidc', 'api_health']:
            return

        # Block all unauthenticated API access.
        # This is for machine-to-machine communication (workers).
        if request.path.startswith('/api/'):
            api_key = request.headers.get('X-API-Key')
            if api_key and api_key == os.environ.get('API_KEY'):
                # API key is valid, now validate worker session for worker-specific endpoints
                # These are endpoints that ONLY workers should call
                if request.endpoint in WORKER_PROTECTED_ENDPOINTS:
                    # These endpoints require session validation
                    hostname = None
                    session_token = None
                    
                    # Extract hostname and session_token from request
                    if request.method == 'POST' and request.is_json:
                        hostname = request.json.get('hostname')
                        session_token = request.json.get('session_token')
                    elif request.method == 'GET':
                        hostname = request.args.get('hostname')
                        session_token = request.args.get('session_token')
                    
                    # Validate session token
                    if not hostname or not session_token:
                        return jsonify(error="Worker endpoints require hostname and session_token"), 400
                    
                    is_valid, error_msg = validate_worker_session(hostname, session_token)
                    if not is_valid:
                        return jsonify(error=error_msg), 403
                
                return # API key is valid, allow access
            return jsonify(error="Authentication required. Invalid or missing API Key."), 401

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
            version=get_project_version(),
            devmode=app.config.get('DEVMODE', False)
        )

# Initialize authentication
setup_auth(app)

def get_arr_ssl_verify():
    """
    Returns whether SSL certificate verification should be enabled for *Arr API calls.
    Can be disabled for development with self-signed certificates, but should
    always be enabled in production to prevent man-in-the-middle attacks.
    """
    return os.environ.get('ARR_SSL_VERIFY', 'true').lower() == 'true'

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

def get_local_time_string(dt_utc, format='%H:%M:%S'):
    """
    Converts a UTC datetime to the configured timezone and formats it as a string.
    
    Args:
        dt_utc: A timezone-aware datetime object in UTC
        format: The strftime format string (default: '%H:%M:%S')
    
    Returns:
        A formatted time string in the configured timezone
    """
    tz_name = os.environ.get('TZ', 'UTC')
    try:
        local_tz = ZoneInfo(tz_name)
        dt_local = dt_utc.astimezone(local_tz)
        return dt_local.strftime(format)
    except (ZoneInfoNotFoundError, ValueError) as e:
        # Fallback to UTC if timezone conversion fails
        logging.warning(f"Could not convert to timezone '{tz_name}': {e}. Using UTC.")
        return dt_utc.strftime(format)
    except Exception as e:
        # Catch any other unexpected errors
        logging.error(f"Unexpected error converting timezone '{tz_name}': {e}. Using UTC.")
        return dt_utc.strftime(format)

# Print a startup banner to the logs
print(f"\nLibrarrarian Web Dashboard v{get_project_version()}\n")

# ===========================
# Database Migrations
# ===========================
TARGET_SCHEMA_VERSION = 12

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
    # Version 7: Add auto-rename after transcode settings for Sonarr/Radarr
    7: [
        "INSERT INTO worker_settings (setting_name, setting_value) VALUES ('sonarr_auto_rename_after_transcode', 'false') ON CONFLICT (setting_name) DO NOTHING;",
        "INSERT INTO worker_settings (setting_name, setting_value) VALUES ('radarr_auto_rename_after_transcode', 'false') ON CONFLICT (setting_name) DO NOTHING;"
    ],
    # Version 8: Add VP9 codec setting
    8: [
        "INSERT INTO worker_settings (setting_name, setting_value) VALUES ('allow_vp9', 'false') ON CONFLICT (setting_name) DO NOTHING;"
    ],
    # Version 9: Add session token for worker uniqueness enforcement
    9: [
        "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS session_token VARCHAR(64);"
    ],
    # Version 10: Add estimated finish time support for transcodes
    10: [
        "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS total_duration REAL;",
        "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS job_start_time TIMESTAMP WITH TIME ZONE;"
    ],
    # Version 11: Add configurable backup time setting
    11: [
        "INSERT INTO worker_settings (setting_name, setting_value) VALUES ('backup_time', '02:00') ON CONFLICT (setting_name) DO NOTHING;"
    ],
    # Version 12: Add backup enable/disable and retention policy settings
    12: [
        "INSERT INTO worker_settings (setting_name, setting_value) VALUES ('backup_enabled', 'true') ON CONFLICT (setting_name) DO NOTHING;",
        "INSERT INTO worker_settings (setting_name, setting_value) VALUES ('backup_retention_days', '7') ON CONFLICT (setting_name) DO NOTHING;"
    ],
}

def run_migrations():
    """Checks the current DB schema version and applies any necessary migrations."""
    # This function is now called before the app starts serving requests.
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
    db_ready_event.wait() # Ensure no DB operations happen until migrations are done.
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
                
                db_user = DB_CONFIG.get('user')
                # Validate db_user to prevent SQL injection
                # Use a whitelist of known safe database user names
                # PostgreSQL identifiers can contain various characters when quoted, but we
                # restrict to simple alphanumeric and underscore for security
                if not db_user or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', db_user):
                    raise ValueError(f"Invalid database user name: {db_user}. Must start with a letter or underscore and contain only alphanumeric characters and underscores.")

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
                        current_file TEXT,
                        session_token VARCHAR(64)
                    );
                """)
                cur.execute(f"GRANT ALL PRIVILEGES ON TABLE nodes TO {db_user};")
                cur.execute(f"GRANT USAGE, SELECT ON SEQUENCE nodes_id_seq TO {db_user};")
                cur.execute(f"ALTER TABLE nodes OWNER TO {db_user};")

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
                cur.execute(f"GRANT ALL PRIVILEGES ON TABLE jobs TO {db_user};")
                cur.execute(f"GRANT USAGE, SELECT ON SEQUENCE jobs_id_seq TO {db_user};")
                cur.execute(f"ALTER TABLE jobs OWNER TO {db_user};")

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS worker_settings (
                        id SERIAL PRIMARY KEY,
                        setting_name VARCHAR(255) UNIQUE NOT NULL,
                        setting_value TEXT
                    );
                """)
                cur.execute(f"GRANT ALL PRIVILEGES ON TABLE worker_settings TO {db_user};")
                cur.execute(f"GRANT USAGE, SELECT ON SEQUENCE worker_settings_id_seq TO {db_user};")
                cur.execute(f"ALTER TABLE worker_settings OWNER TO {db_user};")

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
                cur.execute(f"GRANT ALL PRIVILEGES ON TABLE encoded_files TO {db_user};")
                cur.execute(f"GRANT USAGE, SELECT ON SEQUENCE encoded_files_id_seq TO {db_user};")
                cur.execute(f"ALTER TABLE encoded_files OWNER TO {db_user};")

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS failed_files (
                        id SERIAL PRIMARY KEY,
                        filename TEXT,
                        reason TEXT,
                        log TEXT,
                        failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute(f"GRANT ALL PRIVILEGES ON TABLE failed_files TO {db_user};")
                cur.execute(f"GRANT USAGE, SELECT ON SEQUENCE failed_files_id_seq TO {db_user};")
                cur.execute(f"ALTER TABLE failed_files OWNER TO {db_user};")

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
                cur.execute(f"GRANT ALL PRIVILEGES ON TABLE media_source_types TO {db_user};")
                cur.execute(f"GRANT USAGE, SELECT ON SEQUENCE media_source_types_id_seq TO {db_user};")
                cur.execute(f"ALTER TABLE media_source_types OWNER TO {db_user};")

                cur.execute("""
                    INSERT INTO worker_settings (setting_name, setting_value) VALUES
                        ('rescan_delay_minutes', '0'),
                        ('worker_poll_interval', '30'),
                        ('min_length', '0.5'),
                        ('backup_directory', ''),
                        ('backup_time', '02:00'),
                        ('backup_enabled', 'true'),
                        ('backup_retention_days', '7'),
                        ('hardware_acceleration', 'auto'),
                        ('keep_original', 'false'),
                        ('allow_hevc', 'false'),
                        ('allow_av1', 'false'),
                        ('allow_vp9', 'false'),
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
                        ('lidarr_enabled', 'false'),
                        ('sonarr_auto_rename_after_transcode', 'false'),
                        ('radarr_auto_rename_after_transcode', 'false')
                    ON CONFLICT (setting_name) DO NOTHING;
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INT PRIMARY KEY
                    );
                """)
                cur.execute(f"ALTER TABLE schema_version OWNER TO {db_user};")
                # Insert the target schema version since we just created a fresh database
                # with all tables already at the latest schema.
                cur.execute("INSERT INTO schema_version (version) VALUES (%s) ON CONFLICT DO NOTHING", (TARGET_SCHEMA_VERSION,))
                
                conn.commit()
                print(f"Database initialized at schema version {TARGET_SCHEMA_VERSION}.")

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
            
            # Get total failure count (failed_files + stuck jobs)
            cur.execute("SELECT COUNT(*) as cnt FROM failed_files")
            failures = cur.fetchone()['cnt']
            
            # Count stuck jobs: jobs in 'encoding' status where worker is online and processing higher job IDs
            cur.execute("""
                SELECT COUNT(*) as cnt FROM jobs
                WHERE status = 'encoding'
                AND assigned_to IS NOT NULL
                AND EXISTS (
                    SELECT 1 FROM nodes
                    WHERE nodes.hostname = jobs.assigned_to
                    AND nodes.last_heartbeat > NOW() - INTERVAL '10 minutes'
                )
                AND EXISTS (
                    SELECT 1 FROM jobs AS j2
                    WHERE j2.assigned_to = jobs.assigned_to
                    AND j2.status = 'encoding'
                    AND j2.id > jobs.id
                )
            """)
            stuck_count = cur.fetchone()['cnt']
            failures += stuck_count
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
    """Fetches the detailed list of failed files from the database, including stuck jobs."""
    db = get_db()
    files = []
    db_error = None

    if db is None:
        db_error = "Cannot connect to the PostgreSQL database."
        return files, db_error
    
    try:
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            # Get regular failed files
            cur.execute("SELECT id, filename, reason, failed_at AS reported_at, log, 'failed_file' as type FROM failed_files ORDER BY failed_at DESC")
            files = cur.fetchall()
            
            # Get stuck jobs (jobs in 'encoding' status where worker is online and processing higher job IDs)
            cur.execute("""
                SELECT 
                    jobs.id,
                    jobs.filepath as filename,
                    'Stuck transcode - Worker is online but processing other jobs' as reason,
                    jobs.updated_at as reported_at,
                    'Job appears to have failed silently. Worker came back online and started processing higher job IDs.' as log,
                    'stuck_job' as type
                FROM jobs
                WHERE jobs.status = 'encoding'
                AND jobs.assigned_to IS NOT NULL
                AND EXISTS (
                    SELECT 1 FROM nodes
                    WHERE nodes.hostname = jobs.assigned_to
                    AND nodes.last_heartbeat > NOW() - INTERVAL '10 minutes'
                )
                AND EXISTS (
                    SELECT 1 FROM jobs AS j2
                    WHERE j2.assigned_to = jobs.assigned_to
                    AND j2.status = 'encoding'
                    AND j2.id > jobs.id
                )
                ORDER BY jobs.updated_at DESC
            """)
            stuck_jobs = cur.fetchall()
            files.extend(stuck_jobs)
            
            # Sort all files by reported_at descending
            files = sorted(files, key=lambda x: x['reported_at'], reverse=True)
            
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

def validate_worker_session(hostname, session_token):
    """
    Validates that a worker's session token matches the one stored in the database.
    Returns (is_valid, error_message).
    - is_valid: True if the session is valid, False otherwise
    - error_message: None if valid, otherwise a string describing the issue
    """
    if not hostname or not session_token:
        return False, "Missing hostname or session token"
    
    conn = get_db()
    if not conn:
        return False, "Database connection failed"
    
    cur = None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT session_token, status FROM nodes WHERE hostname = %s", (hostname,))
        node = cur.fetchone()
        
        if not node:
            # Node doesn't exist yet - worker must register first
            return False, f"Worker '{hostname}' is not registered. Please register via /api/register_worker first."
        
        stored_token = node.get('session_token')
        if not stored_token:
            # No session token stored yet - this shouldn't happen in normal flow
            # but we'll allow it for backward compatibility
            return True, None
        
        if stored_token != session_token:
            # Session token mismatch - reject this worker
            return False, f"Worker '{hostname}' is already registered with a different session. Another worker with the same hostname is active."
        
        # Token matches - this is the legitimate worker
        return True, None
    except Exception as e:
        print(f"Error validating worker session: {e}")
        return False, f"Session validation error: {e}"
    finally:
        if cur:
            cur.close()

# ===========================
# Flask Routes
# ===========================
@app.route('/')
def dashboard():
    """Renders the main dashboard page."""
    # Fetch cluster status and worker settings
    nodes, fail_count, db_error = get_cluster_status()
    settings, settings_db_error = get_worker_settings()

    # Format node data for templating
    for node in nodes:
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

@app.route('/api/health')
def api_health():
    """A dedicated health check endpoint that waits for the DB to be ready."""
    if db_ready_event.is_set():
        return "OK", 200
    else:
        return "Database not ready", 503

@app.route('/api/register_worker', methods=['POST'])
def register_worker():
    """
    Endpoint for workers to register themselves with a unique session token.
    This prevents multiple workers with the same hostname from operating simultaneously.
    """
    data = request.json
    hostname = data.get('hostname')
    session_token = data.get('session_token')
    version = data.get('version', 'unknown')
    
    if not hostname or not session_token:
        return jsonify({"error": "hostname and session_token are required"}), 400
    
    print(f"[{datetime.now()}] Worker registration request from '{hostname}' with session token")
    
    conn = get_db()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if a node with this hostname already exists
        cur.execute("SELECT session_token, status, last_heartbeat FROM nodes WHERE hostname = %s", (hostname,))
        existing_node = cur.fetchone()
        
        if existing_node:
            stored_token = existing_node.get('session_token')
            last_heartbeat = existing_node.get('last_heartbeat')
            
            # If there's already a session token and it's different, reject the registration
            if stored_token and stored_token != session_token:
                # Check if the existing worker is still active (heartbeat within last 5 minutes)
                if last_heartbeat:
                    time_since_heartbeat = (datetime.now(timezone.utc) - last_heartbeat.replace(tzinfo=timezone.utc)).total_seconds()
                    
                    if time_since_heartbeat < WORKER_SESSION_TIMEOUT_SECONDS:
                        print(f"[{datetime.now()}] Registration rejected: Worker '{hostname}' is already active")
                        return jsonify({
                            "error": f"A worker with hostname '{hostname}' is already active in the cluster.",
                            "message": "Please stop the existing worker or choose a different hostname.",
                            "rejected": True
                        }), 409  # 409 Conflict
                    else:
                        # Old worker is stale, allow the new one to take over
                        print(f"[{datetime.now()}] Existing worker '{hostname}' is stale (last heartbeat {int(time_since_heartbeat)}s ago). Allowing new worker to register.")
                
            # If the session token matches or there's no token, update it
            cur.execute("""
                UPDATE nodes 
                SET session_token = %s, version = %s, last_heartbeat = NOW(), connected_at = NOW(), status = 'booting'
                WHERE hostname = %s
            """, (session_token, version, hostname))
        else:
            # New worker - insert a new record
            cur.execute("""
                INSERT INTO nodes (hostname, session_token, version, status, last_heartbeat, connected_at)
                VALUES (%s, %s, %s, 'booting', NOW(), NOW())
            """, (hostname, session_token, version))
        
        conn.commit()
        print(f"[{datetime.now()}] Worker '{hostname}' registered successfully")
        return jsonify({"success": True, "message": f"Worker '{hostname}' registered successfully"}), 200
        
    except Exception as e:
        conn.rollback()
        print(f"[{datetime.now()}] Worker registration error: {e}")
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500
    finally:
        cur.close()

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
        logout_url = app.oauth.oidc_provider.server_metadata.get('end_session_endpoint')
        if logout_url:
            return redirect(logout_url)
    return redirect(url_for('login'))

@app.route('/options', methods=['POST'])
def options():
    """
    Handles the form submission for worker settings from the main dashboard.
    This route now follows the Post-Redirect-Get pattern and uses a single
    atomic transaction to save all settings.
    """
    # Validate backup_retention_days on server-side
    retention_days_raw = request.form.get('backup_retention_days', '7')
    try:
        retention_days = int(retention_days_raw)
        if retention_days < 1:
            retention_days = 1
        elif retention_days > 365:
            retention_days = 365
        retention_days_str = str(retention_days)
    except (ValueError, TypeError):
        retention_days_str = '7'  # Default to 7 if invalid
    
    # Convert hours to minutes for backward compatibility with existing code
    rescan_hours = request.form.get('rescan_delay_hours', '0')
    try:
        rescan_minutes = str(round(float(rescan_hours) * 60))
    except (ValueError, TypeError):
        rescan_minutes = '0'
    
    settings_to_update = {
        'media_scanner_type': request.form.get('media_scanner_type', 'plex'),
        'rescan_delay_minutes': rescan_minutes,
        'worker_poll_interval': request.form.get('worker_poll_interval', '30'),
        'min_length': request.form.get('min_length', '0.5'),
        'backup_directory': request.form.get('backup_directory', ''),
        'backup_time': request.form.get('backup_time', '02:00'),
        'backup_enabled': 'true' if 'backup_enabled' in request.form else 'false',
        'backup_retention_days': retention_days_str,
        'hardware_acceleration': request.form.get('hardware_acceleration', 'auto'),
        'keep_original': 'true' if 'keep_original' in request.form else 'false',
        'allow_hevc': 'true' if 'allow_hevc' in request.form else 'false',
        'allow_av1': 'true' if 'allow_av1' in request.form else 'false',
        'allow_vp9': 'true' if 'allow_vp9' in request.form else 'false',
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
    settings_to_update['radarr_send_to_queue'] = 'true' if 'radarr_send_to_queue' in request.form else 'false'
    settings_to_update['lidarr_send_to_queue'] = 'true' if 'lidarr_send_to_queue' in request.form else 'false'
    settings_to_update['sonarr_auto_rename_after_transcode'] = 'true' if 'sonarr_auto_rename_after_transcode' in request.form else 'false'
    settings_to_update['radarr_auto_rename_after_transcode'] = 'true' if 'radarr_auto_rename_after_transcode' in request.form else 'false'
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
                # Items are now hidden when media_type is set to 'none' (Ignore)
                is_hidden = (media_type == 'none')
                cur.execute("""
                    INSERT INTO media_source_types (source_name, scanner_type, media_type, is_hidden)
                    VALUES (%s, 'plex', %s, %s)
                    ON CONFLICT (source_name, scanner_type) DO UPDATE SET media_type = EXCLUDED.media_type, is_hidden = EXCLUDED.is_hidden;
                """, (source_name, media_type, is_hidden))

            for source_name in all_internal_sources:
                media_type = request.form.get(f'type_internal_{source_name}')
                # Items are now hidden when media_type is set to 'none' (Ignore)
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

@app.route('/api/backup/now', methods=['POST'])
def api_backup_now():
    """Triggers an immediate database backup."""
    try:
        success, message, backup_file = perform_database_backup()
        if success:
            return jsonify(success=True, message=message, backup_file=backup_file)
        else:
            return jsonify(success=False, error=message), 500
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/backup/files', methods=['GET'])
def api_backup_files():
    """
    Lists all backup files with metadata.
    Note: Authentication is enforced by the @app.before_request hook.
    """
    try:
        # Database backups are stored in a fixed location, not the user-configurable backup_directory
        backup_dir = '/data/backup'
        
        if not os.path.exists(backup_dir):
            return jsonify(success=True, files=[])
        
        backup_files = []
        for filename in os.listdir(backup_dir):
            if filename.endswith('.tar.gz') or (filename.startswith('librarrarian_backup_') and filename.endswith('.sql.gz')):
                filepath = os.path.join(backup_dir, filename)
                stat = os.stat(filepath)
                
                backup_files.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'size_mb': round(stat.st_size / (1024 * 1024), 2),
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'mtime': stat.st_mtime  # Store the timestamp for proper sorting
                })
        
        # Sort by creation time (using timestamp), newest first
        backup_files.sort(key=lambda x: x['mtime'], reverse=True)
        
        # Remove the mtime field before returning to client
        for f in backup_files:
            del f['mtime']
        
        return jsonify(success=True, files=backup_files)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/backup/download/<filename>', methods=['GET'])
def api_backup_download(filename):
    """
    Download a specific backup file.
    Note: Authentication is enforced by the @app.before_request hook.
    """
    try:
        # Sanitize filename to prevent directory traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify(success=False, error="Invalid filename"), 400
        
        # Database backups are stored in a fixed location, not the user-configurable backup_directory
        backup_dir = '/data/backup'
        
        filepath = os.path.join(backup_dir, filename)
        
        if not os.path.exists(filepath):
            return jsonify(success=False, error="File not found"), 404
        
        # Send file for download
        from flask import send_file
        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/backup/delete/<filename>', methods=['POST'])
def api_backup_delete(filename):
    """
    Delete a specific backup file.
    Note: Authentication is enforced by the @app.before_request hook.
    """
    try:
        # Sanitize filename to prevent directory traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify(success=False, error="Invalid filename"), 400
        
        # Database backups are stored in a fixed location, not the user-configurable backup_directory
        backup_dir = '/data/backup'
        
        filepath = os.path.join(backup_dir, filename)
        
        if not os.path.exists(filepath):
            return jsonify(success=False, error="File not found"), 404
        
        os.remove(filepath)
        print(f"[{datetime.now()}] Backup file deleted by user: {filename}")
        
        return jsonify(success=True, message=f"Backup file {filename} deleted successfully")
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/jobs/clear', methods=['POST'])
def api_clear_jobs():
    """
    Clears jobs from the queue. This now clears all 'pending' transcode/cleanup jobs
    and ALL jobs (regardless of status) that are internal-only (Rename, Quality Mismatch).
    """
    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute("DELETE FROM jobs WHERE status = 'pending' OR job_type IN ('Rename Job', 'Quality Mismatch');")
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
            rowcount = cur.rowcount
        db.commit()
        if rowcount == 0:
            return jsonify(success=False, error="Job not found."), 404
        return jsonify(success=True, message=f"Job {job_id} deleted successfully.")
    except Exception as e:
        print(f"Error deleting job {job_id}: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/jobs/requeue/<int:job_id>', methods=['POST'])
def api_requeue_job(job_id):
    """Resets a job back to pending status, clearing its assignment and updating timestamp."""
    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET status = 'pending', assigned_to = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (job_id,)
            )
            rowcount = cur.rowcount
        db.commit()
        if rowcount == 0:
            return jsonify(success=False, error="Job not found."), 404
        return jsonify(success=True, message=f"Job {job_id} re-added to queue successfully.")
    except Exception as e:
        print(f"Error re-queuing job {job_id}: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/api/jobs', methods=['GET'])
def api_jobs():
    """Returns a paginated and optionally filtered list of the current job queue as JSON."""
    db = get_db()
    jobs = []
    db_error = None
    total_jobs = 0
    page = request.args.get('page', 1, type=int)
    per_page = 50 # Number of jobs per page
    offset = (page - 1) * per_page
    
    # Filtering parameters
    filter_type = request.args.get('type', '')  # Filter by job_type
    filter_status = request.args.get('status', '')  # Filter by status

    if db is None:
        db_error = "Cannot connect to the PostgreSQL database."
        return jsonify(jobs=jobs, db_error=db_error, total_jobs=0, page=page, per_page=per_page)

    try:
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            # Build WHERE clause dynamically based on filters
            where_clauses = []
            params = []
            
            if filter_type:
                where_clauses.append("jobs.job_type = %s")
                params.append(filter_type)
            
            if filter_status:
                where_clauses.append("jobs.status = %s")
                params.append(filter_status)
            
            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)
            
            # Query for the paginated list of jobs
            # This custom sort order brings 'encoding' jobs to the top, followed by 'pending'.
            # We also calculate the age of the job in minutes to detect stuck jobs.
            # For encoding jobs, we also check the worker's last_heartbeat to determine if the worker is stuck.
            # We also check if the worker is processing higher job IDs (indicating this job failed silently)
            # NOTE: The subquery for higher_job_id_by_same_worker executes per row. For better performance
            # with large job queues, consider using a window function (LEAD/LAG) or adding an index on
            # (assigned_to, status, id). Current implementation is acceptable for typical queue sizes (<10k jobs).
            # Also consider adding an index on jobs.assigned_to and nodes.hostname if needed.
            query = f"""
                SELECT jobs.*,
                       EXTRACT(EPOCH FROM (NOW() - jobs.updated_at)) / 60 AS age_minutes,
                       EXTRACT(EPOCH FROM (NOW() - nodes.last_heartbeat)) / 60 AS minutes_since_heartbeat,
                       (SELECT MAX(id) FROM jobs AS j2 WHERE j2.assigned_to = jobs.assigned_to AND j2.status = 'encoding' AND j2.id > jobs.id) AS higher_job_id_by_same_worker
                FROM jobs
                LEFT JOIN nodes ON jobs.assigned_to = nodes.hostname
                {where_sql}
                ORDER BY
                    CASE jobs.status
                        WHEN 'encoding' THEN 1
                        WHEN 'pending' THEN 2
                        WHEN 'failed' THEN 3
                        ELSE 4
                    END,
                    jobs.created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([per_page, offset])
            cur.execute(query, params)
            jobs = cur.fetchall()
            for job in jobs:
                job['created_at'] = job['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                # Mark job as stuck if worker is online and processing higher job IDs
                job['is_stuck'] = (
                    job['status'] == 'encoding' and 
                    job['assigned_to'] and 
                    job['minutes_since_heartbeat'] is not None and 
                    job['minutes_since_heartbeat'] < 10 and  # Worker is still online
                    job['higher_job_id_by_same_worker'] is not None  # Worker is processing higher job IDs
                )
            
            # Query for the total number of jobs to calculate total pages (respecting filters)
            # count_params should only include the filter parameters, not LIMIT and OFFSET
            count_query = f"SELECT COUNT(*) FROM jobs {where_sql}"
            count_params = params[:-2] if len(params) > 2 else []  # Exclude LIMIT and OFFSET params
            cur.execute(count_query, count_params)
            total_jobs = cur.fetchone()['count']

    except Exception as e:
        db_error = f"Database query failed: {e}"

    return jsonify(jobs=jobs, db_error=db_error, total_jobs=total_jobs, page=page, per_page=per_page)

@app.route('/api/jobs/filters', methods=['GET'])
def api_jobs_filters():
    """Returns the distinct job types and statuses available for filtering."""
    db = get_db()
    job_types = []
    statuses = []
    db_error = None

    if db is None:
        db_error = "Cannot connect to the PostgreSQL database."
        return jsonify(job_types=job_types, statuses=statuses, db_error=db_error)

    try:
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT DISTINCT job_type FROM jobs ORDER BY job_type")
            job_types = [row['job_type'] for row in cur.fetchall()]
            
            cur.execute("SELECT DISTINCT status FROM jobs ORDER BY status")
            statuses = [row['status'] for row in cur.fetchall()]

    except Exception as e:
        db_error = f"Database query failed: {e}"

    return jsonify(job_types=job_types, statuses=statuses, db_error=db_error)

@app.route('/api/status')
def api_status():
    """Returns cluster status data as JSON."""
    nodes, fail_count, db_error = get_cluster_status()
    settings, _ = get_worker_settings()
    
    # Add the color key for the frontend to use
    for node in nodes:
        # Add the 'percent' key for the client-side rendering
        node['percent'] = int(node.get('progress') or 0)

        # Re-implement Speed and Codec for the UI
        node['speed'] = round(node.get('fps', 0) / 24, 1) if node.get('fps') else 0.0
        node['codec'] = 'hevc'
        
        # Calculate estimated finish time
        if node.get('total_duration') and node.get('job_start_time') and node.get('progress', 0) > 0:
            try:
                total_duration = float(node['total_duration'])
                progress = float(node.get('progress', 0))
                job_start = node['job_start_time']
                
                # Calculate elapsed time
                elapsed = (datetime.now(timezone.utc) - job_start).total_seconds()
                
                # Calculate estimated total time based on current progress
                if progress > 0:
                    estimated_total_time = (elapsed / progress) * 100
                    remaining_seconds = estimated_total_time - elapsed
                    
                    if remaining_seconds > 0:
                        eta_utc = datetime.now(timezone.utc) + timedelta(seconds=remaining_seconds)
                        # Convert to configured timezone (from TZ environment variable)
                        node['eta'] = get_local_time_string(eta_utc)
                        node['eta_seconds'] = int(remaining_seconds)
                    else:
                        node['eta'] = 'N/A'
                        node['eta_seconds'] = 0
                else:
                    node['eta'] = 'Calculating...'
                    node['eta_seconds'] = 0
            except Exception as e:
                print(f"Error calculating ETA: {e}")
                node['eta'] = 'N/A'
                node['eta_seconds'] = 0
        else:
            node['eta'] = None
            node['eta_seconds'] = 0

    # Get current time in configured timezone
    last_updated_time = get_local_time_string(datetime.now(timezone.utc))
    
    return jsonify(
        nodes=nodes,
        fail_count=fail_count,
        db_error=db_error,
        queue_paused=settings.get('pause_job_distribution', {}).get('setting_value') == 'true',
        last_updated=last_updated_time
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

@app.route('/api/nodes/start-all', methods=['POST'])
def api_start_all_nodes():
    """API endpoint to start all active nodes."""
    db = get_db()
    if db is None:
        return jsonify(success=False, error="Cannot connect to the PostgreSQL database."), 500
    
    try:
        with db.cursor() as cur:
            # Start all nodes that are either idle or offline (not already running or paused)
            # Only update command, not last_heartbeat (heartbeat should only be updated by workers)
            cur.execute("""
                UPDATE nodes 
                SET command = 'running' 
                WHERE last_heartbeat > NOW() - INTERVAL '5 minutes' 
                AND command IN ('idle', 'offline')
            """)
            affected_count = cur.rowcount
        db.commit()
        return jsonify(success=True, message=f"Start command sent to {affected_count} node(s).", count=affected_count)
    except Exception as e:
        return jsonify(success=False, error=f"Database query failed: {e}"), 500

@app.route('/api/nodes/stop-all', methods=['POST'])
def api_stop_all_nodes():
    """API endpoint to stop all active nodes."""
    db = get_db()
    if db is None:
        return jsonify(success=False, error="Cannot connect to the PostgreSQL database."), 500
    
    try:
        with db.cursor() as cur:
            # Stop all nodes that are running or paused (not already idle)
            # Only update command, not last_heartbeat (heartbeat should only be updated by workers)
            cur.execute("""
                UPDATE nodes 
                SET command = 'idle' 
                WHERE last_heartbeat > NOW() - INTERVAL '5 minutes' 
                AND command IN ('running', 'paused')
            """)
            affected_count = cur.rowcount
        db.commit()
        return jsonify(success=True, message=f"Stop command sent to {affected_count} node(s).", count=affected_count)
    except Exception as e:
        return jsonify(success=False, error=f"Database query failed: {e}"), 500

@app.route('/api/nodes/pause-all', methods=['POST'])
def api_pause_all_nodes():
    """API endpoint to pause all running nodes."""
    db = get_db()
    if db is None:
        return jsonify(success=False, error="Cannot connect to the PostgreSQL database."), 500
    
    try:
        with db.cursor() as cur:
            # Pause all nodes that are running (not already paused or idle)
            # Only update command, not last_heartbeat (heartbeat should only be updated by workers)
            cur.execute("""
                UPDATE nodes 
                SET command = 'paused' 
                WHERE last_heartbeat > NOW() - INTERVAL '5 minutes' 
                AND command = 'running'
            """)
            affected_count = cur.rowcount
        db.commit()
        return jsonify(success=True, message=f"Pause command sent to {affected_count} node(s).", count=affected_count)
    except Exception as e:
        return jsonify(success=False, error=f"Database query failed: {e}"), 500

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
radarr_rename_scan_event = threading.Event()
lidarr_rename_scan_event = threading.Event()
scan_cancel_event = threading.Event()
cleanup_scanner_lock = threading.Lock()
cleanup_scan_now_event = threading.Event()

# --- Global state for scan progress ---
scan_progress_state = {
    "is_running": False, "current_step": "", "total_steps": 0, "progress": 0, "scan_source": "", "scan_type": ""
}

def arr_background_thread():
    """Waits for triggers to run Sonarr/Radarr/Lidarr scans (rename, quality, etc.)."""
    while True:
        # Check all events without blocking using is_set() first
        # This prevents the sequential blocking that was causing delays
        if sonarr_rename_scan_event.is_set():
            sonarr_rename_scan_event.clear()
            print(f"[{datetime.now()}] Triggering Sonarr rename scan in background thread.")
            scan_thread = threading.Thread(target=run_sonarr_rename_scan)
            scan_thread.start()

        if sonarr_quality_scan_event.is_set():
            sonarr_quality_scan_event.clear()
            print(f"[{datetime.now()}] Triggering Sonarr quality scan in background thread.")
            scan_thread = threading.Thread(target=run_sonarr_quality_scan)
            scan_thread.start()

        if radarr_rename_scan_event.is_set():
            radarr_rename_scan_event.clear()
            print(f"[{datetime.now()}] Triggering Radarr rename scan in background thread.")
            scan_thread = threading.Thread(target=run_radarr_rename_scan)
            scan_thread.start()

        if lidarr_rename_scan_event.is_set():
            lidarr_rename_scan_event.clear()
            print(f"[{datetime.now()}] Triggering Lidarr rename scan in background thread.")
            scan_thread = threading.Thread(target=run_lidarr_rename_scan)
            scan_thread.start()

        time.sleep(0.5)  # Check events every 500ms for good responsiveness without high CPU usage

def run_sonarr_rename_scan():
    """
    Handles Sonarr integration. Can either trigger Sonarr's API directly
    or add 'rename' jobs to the local queue for a worker to process.
    """
    with app.app_context():
        # Clear the cancel event first, before trying to acquire the lock
        scan_cancel_event.clear()
        
        # This function is now fully self-contained and runs in its own thread.
        if not scanner_lock.acquire(blocking=False):
            print(f"[{datetime.now()}] Rename scan trigger ignored: Another scan is already in progress.")
            # Reset the progress state since the API endpoint set it optimistically
            scan_progress_state.update({"is_running": False, "current_step": "Another scan is already in progress.", "progress": 0, "scan_source": "", "scan_type": ""})
            return

        scan_progress_state.update({"is_running": True, "current_step": "Initializing rename scan...", "total_steps": 0, "progress": 0, "scan_source": "sonarr", "scan_type": "rename"})

        try:
            settings, db_error = get_worker_settings()
            if db_error:
                scan_progress_state["current_step"] = "Error: Database not available."
                return
    
            if settings.get('sonarr_enabled', {}).get('setting_value') != 'true':
                scan_progress_state["current_step"] = "Error: Sonarr integration is disabled."
                return
    
            host = settings.get('sonarr_host', {}).get('setting_value')
            api_key = settings.get('sonarr_api_key', {}).get('setting_value')
            send_to_queue = settings.get('sonarr_send_to_queue', {}).get('setting_value') == 'true'
    
            if not host or not api_key:
                scan_progress_state["current_step"] = "Error: Sonarr is not configured."
                return
    
            print(f"[{datetime.now()}] Sonarr Rename Scanner: Starting deep scan...")
            headers = {'X-Api-Key': api_key}
            base_url = host.rstrip('/')
            series_res = requests.get(f"{base_url}/api/v3/series", headers=headers, timeout=10, verify=get_arr_ssl_verify())
            series_res.raise_for_status()
            all_series = series_res.json()
            
            scan_progress_state["total_steps"] = len(all_series)
            conn = get_db()
            cur = conn.cursor()
            new_jobs_found = 0 
            renames_performed = 0 # NEW: Counter for direct renames
    
            for i, series in enumerate(all_series):
                if scan_cancel_event.is_set():
                    print("Rename scan cancelled by user.")
                    scan_progress_state["current_step"] = "Scan cancelled by user."
                    return
    
                series_title = series.get('title', 'Unknown Series')
                scan_progress_state.update({"current_step": f"Analyzing: {series_title}", "progress": i + 1})
    
                # This is the correct pattern: trigger a scan, then check for results.
                requests.post(f"{base_url}/api/v3/command", headers=headers, json={'name': 'RescanSeries', 'seriesId': series['id']}, timeout=10, verify=get_arr_ssl_verify())
                time.sleep(2) # Give Sonarr a moment to process before we query
                rename_res = requests.get(f"{base_url}/api/v3/rename?seriesId={series['id']}", headers=headers, timeout=10, verify=get_arr_ssl_verify())
                for episode in rename_res.json():
                    filepath = episode.get('existingPath')
                    if filepath:
                        # Determine job status or perform direct rename based on 'send_to_queue' setting
                        if send_to_queue:
                            job_status = 'awaiting_approval' # New behavior: if selected, awaiting approval
                            metadata = {
                                'source': 'sonarr',
                                'seriesTitle': series['title'],
                                'seasonNumber': episode.get('seasonNumber'),
                                'episodeNumber': episode.get('episodeNumbers', [0])[0],
                                'episodeTitle': "Episode", 'quality': "N/A",
                                'episodeFileId': episode.get('episodeFileId'),
                                'seriesId': series.get('id')
                            }
                            cur.execute("INSERT INTO jobs (filepath, job_type, status, metadata) VALUES (%s, 'Rename Job', %s, %s) ON CONFLICT (filepath) DO NOTHING", (filepath, job_status, json.dumps(metadata)))
                            if cur.rowcount > 0: new_jobs_found += 1
                        else:
                            # New behavior: if not selected, perform rename directly via Sonarr API
                            print(f"  -> Auto-renaming episode file {filepath} via Sonarr API.")
                            payload = {"name": "RenameFiles", "seriesId": series['id'], "files": [episode.get('episodeFileId')]}
                            rename_cmd_res = requests.post(f"{base_url}/api/v3/command", headers=headers, json=payload, timeout=20, verify=get_arr_ssl_verify())
                            rename_cmd_res.raise_for_status() 
                            renames_performed += 1
    
            conn.commit()
            if send_to_queue:
                message = f"Sonarr deep scan complete. Found {new_jobs_found} new files to rename. Added to queue for approval."
            else:
                message = f"Sonarr deep scan complete. Performed {renames_performed} automatic renames." 
            scan_progress_state["current_step"] = message
            print(f"[{datetime.now()}] {message}")

        except Exception as e:
            error_message = f"An error occurred during the deep scan: {e}"
            print(f"[{datetime.now()}] {error_message}")
            scan_progress_state["current_step"] = f"Error: {e}"
        finally:
            # Only delay if the scan wasn't cancelled, to allow immediate retry
            if not scan_cancel_event.is_set():
                time.sleep(10)
            scan_progress_state.update({"is_running": False, "current_step": "", "progress": 0, "scan_source": "", "scan_type": ""})
            if scanner_lock.locked():
                scanner_lock.release()

def run_sonarr_quality_scan():
    """
    Scans Sonarr for quality mismatches. Compares each episode file's quality
    against the series' quality profile to identify files that don't meet the
    profile's cutoff. Creates 'Quality Mismatch' jobs for investigation.
    
    Logic:
    1. Get all quality profiles from Sonarr
    2. For each series, get its quality profile
    3. For each episode with a file, compare file quality against profile cutoff
    4. If file quality doesn't meet cutoff, create a quality mismatch job
    """
    with app.app_context():
        # Clear the cancel event first, before trying to acquire the lock
        scan_cancel_event.clear()
        
        if not scanner_lock.acquire(blocking=False):
            print(f"[{datetime.now()}] Quality scan trigger ignored: Another scan is already in progress.")
            # Reset the progress state since the API endpoint set it optimistically
            scan_progress_state.update({"is_running": False, "current_step": "Another scan is already in progress.", "progress": 0, "scan_source": "", "scan_type": ""})
            return

        scan_progress_state.update({"is_running": True, "current_step": "Initializing quality scan...", "total_steps": 0, "progress": 0, "scan_source": "sonarr", "scan_type": "quality"})
        
        try:
            settings, db_error = get_worker_settings()
            if db_error:
                scan_progress_state["current_step"] = "Error: Database not available."
                return

            host = settings.get('sonarr_host', {}).get('setting_value')
            api_key = settings.get('sonarr_api_key', {}).get('setting_value')

            if not host or not api_key:
                scan_progress_state["current_step"] = "Error: Sonarr is not configured."
                return

            print(f"[{datetime.now()}] Sonarr Quality Scanner: Starting scan...")
            headers = {'X-Api-Key': api_key}
            base_url = host.rstrip('/')

            # Fetch quality profiles to get profile names for logging
            profiles_res = requests.get(f"{base_url}/api/v3/qualityprofile", headers=headers, timeout=10, verify=get_arr_ssl_verify())
            profiles_res.raise_for_status()
            quality_profiles = {p['id']: {'name': p['name']} for p in profiles_res.json()}

            series_res = requests.get(f"{base_url}/api/v3/series", headers=headers, timeout=10, verify=get_arr_ssl_verify())
            series_res.raise_for_status()
            all_series = series_res.json()

            scan_progress_state["total_steps"] = len(all_series)
            conn = get_db()
            cur = conn.cursor()
            new_jobs_found = 0
            # Track mismatches per show for summarized logging
            shows_with_mismatches = {}

            for i, series in enumerate(all_series):
                if scan_cancel_event.is_set():
                    print("Quality scan cancelled by user.")
                    scan_progress_state["current_step"] = "Scan cancelled by user."
                    return

                series_title = series.get('title', 'Unknown Series')
                scan_progress_state.update({"current_step": f"Checking: {series_title}", "progress": i + 1})

                profile = quality_profiles.get(series.get('qualityProfileId'))
                if not profile:
                    continue  # Skip series without a valid quality profile

                # Fetch episodes with episode file data included
                # The includeEpisodeFile parameter ensures we get quality info
                episodes_res = requests.get(
                    f"{base_url}/api/v3/episode?seriesId={series['id']}&includeEpisodeFile=true",
                    headers=headers, timeout=20, verify=get_arr_ssl_verify()
                )
                episodes_res.raise_for_status()

                series_mismatch_count = 0
                for episode in episodes_res.json():
                    # Only check episodes that have a file
                    if not episode.get('hasFile'):
                        continue
                    
                    episode_file = episode.get('episodeFile')
                    if not episode_file:
                        continue
                    
                    # Check if the quality cutoff is not met
                    # Sonarr API provides this flag directly when episodeFile is included
                    quality_cutoff_not_met = episode_file.get('qualityCutoffNotMet', False)
                    
                    if quality_cutoff_not_met:
                        filepath = episode_file.get('path', '')
                        file_quality = episode_file.get('quality', {}).get('quality', {})
                        file_quality_name = file_quality.get('name', 'Unknown')
                        
                        metadata = {
                            'source': 'sonarr',
                            'job_class': 'quality_mismatch',
                            'seriesTitle': series['title'],
                            'seasonNumber': episode.get('seasonNumber'),
                            'episodeNumber': episode.get('episodeNumber'),
                            'episodeTitle': episode.get('title', 'Unknown'),
                            'file_quality': file_quality_name,
                            'profile_quality': profile['name'],
                            'seriesId': series['id'],
                            'episodeId': episode.get('id'),
                            'episodeFileId': episode_file.get('id')
                        }
                        
                        cur.execute(
                            "INSERT INTO jobs (filepath, job_type, status, metadata) VALUES (%s, 'Quality Mismatch', 'pending', %s) ON CONFLICT (filepath) DO NOTHING",
                            (filepath, json.dumps(metadata))
                        )
                        if cur.rowcount > 0:
                            new_jobs_found += 1
                            series_mismatch_count += 1

                # Track shows with mismatches for summary
                if series_mismatch_count > 0:
                    shows_with_mismatches[series_title] = series_mismatch_count

            conn.commit()
            
            # Log summary by show instead of every individual file
            if shows_with_mismatches:
                print(f"[{datetime.now()}] Shows with quality mismatches:")
                for show_title, count in shows_with_mismatches.items():
                    print(f"  -> {show_title}: {count} episode(s)")
            
            message = f"Sonarr quality scan complete. Found {new_jobs_found} potential mismatches across {len(shows_with_mismatches)} shows."
            scan_progress_state["current_step"] = message
            print(f"[{datetime.now()}] {message}")
        except Exception as e:
            error_message = f"An error occurred during the quality scan: {e}"
            print(f"[{datetime.now()}] {error_message}")
            scan_progress_state["current_step"] = f"Error: {e}"
        finally:
            # Only delay if the scan wasn't cancelled, to allow immediate retry
            if not scan_cancel_event.is_set():
                time.sleep(10)
            scan_progress_state.update({"is_running": False, "current_step": "", "progress": 0, "scan_source": "", "scan_type": ""})
            if scanner_lock.locked():
                scanner_lock.release()


def run_radarr_rename_scan():
    """
    Handles Radarr integration. Can either trigger Radarr's API directly
    or add 'rename' jobs to the local queue for a worker to process.
    """
    with app.app_context():
        # Clear the cancel event first, before trying to acquire the lock
        scan_cancel_event.clear()
        
        # This function is now fully self-contained and runs in its own thread.
        if not scanner_lock.acquire(blocking=False):
            print(f"[{datetime.now()}] Radarr rename scan trigger ignored: Another scan is already in progress.")
            # Reset the progress state since the API endpoint set it optimistically
            scan_progress_state.update({"is_running": False, "current_step": "Another scan is already in progress.", "progress": 0, "scan_source": "", "scan_type": ""})
            return

        scan_progress_state.update({"is_running": True, "current_step": "Initializing Radarr rename scan...", "total_steps": 0, "progress": 0, "scan_source": "radarr", "scan_type": "rename"})

        try:
            settings, db_error = get_worker_settings()
            if db_error:
                scan_progress_state["current_step"] = "Error: Database not available."
                return
    
            if settings.get('radarr_enabled', {}).get('setting_value') != 'true':
                scan_progress_state["current_step"] = "Error: Radarr integration is disabled."
                return
    
            host = settings.get('radarr_host', {}).get('setting_value')
            api_key = settings.get('radarr_api_key', {}).get('setting_value')
            send_to_queue = settings.get('radarr_send_to_queue', {}).get('setting_value') == 'true'
    
            if not host or not api_key:
                scan_progress_state["current_step"] = "Error: Radarr is not configured."
                return
    
            print(f"[{datetime.now()}] Radarr Rename Scanner: Starting deep scan...")
            headers = {'X-Api-Key': api_key}
            base_url = host.rstrip('/')
            movies_res = requests.get(f"{base_url}/api/v3/movie", headers=headers, timeout=10, verify=get_arr_ssl_verify())
            movies_res.raise_for_status()
            all_movies = movies_res.json()
            
            scan_progress_state["total_steps"] = len(all_movies)
            conn = get_db()
            cur = conn.cursor()
            new_jobs_found = 0 
            renames_performed = 0 # Counter for direct renames
    
            for i, movie in enumerate(all_movies):
                if scan_cancel_event.is_set():
                    print("Radarr rename scan cancelled by user.")
                    scan_progress_state["current_step"] = "Scan cancelled by user."
                    return
    
                movie_title = movie.get('title', 'Unknown Movie')
                scan_progress_state.update({"current_step": f"Analyzing: {movie_title}", "progress": i + 1})

                # This is the correct pattern: trigger a rescan, then check for results.
                requests.post(f"{base_url}/api/v3/command", headers=headers, json={'name': 'RescanMovie', 'movieId': movie['id']}, timeout=10, verify=get_arr_ssl_verify())
                time.sleep(2) # Give Radarr a moment to process before we query
                rename_res = requests.get(f"{base_url}/api/v3/rename?movieId={movie['id']}", headers=headers, timeout=10, verify=get_arr_ssl_verify())
                for rename_item in rename_res.json():
                    filepath = rename_item.get('existingPath')
                    if filepath:
                        # Determine job status or perform direct rename based on 'send_to_queue' setting
                        if send_to_queue:
                            job_status = 'awaiting_approval' # If selected, awaiting approval
                            metadata = {
                                'source': 'radarr',
                                'movieTitle': movie['title'],
                                'movieId': movie.get('id'),
                                'movieFileId': rename_item.get('movieFileId')
                            }
                            cur.execute("INSERT INTO jobs (filepath, job_type, status, metadata) VALUES (%s, 'Rename Job', %s, %s) ON CONFLICT (filepath) DO NOTHING", (filepath, job_status, json.dumps(metadata)))
                            if cur.rowcount > 0: new_jobs_found += 1
                        else:
                            # Perform rename directly via Radarr API
                            print(f"  -> Auto-renaming movie file {filepath} via Radarr API.")
                            payload = {"name": "RenameFiles", "movieId": movie['id'], "files": [rename_item.get('movieFileId')]}
                            rename_cmd_res = requests.post(f"{base_url}/api/v3/command", headers=headers, json=payload, timeout=20, verify=get_arr_ssl_verify())
                            rename_cmd_res.raise_for_status() 
                            renames_performed += 1
    
            conn.commit()
            if send_to_queue:
                message = f"Radarr deep scan complete. Found {new_jobs_found} new files to rename. Added to queue for approval."
            else:
                message = f"Radarr deep scan complete. Performed {renames_performed} automatic renames." 
            scan_progress_state["current_step"] = message
            print(f"[{datetime.now()}] {message}")

        except Exception as e:
            error_message = f"An error occurred during the Radarr deep scan: {e}"
            print(f"[{datetime.now()}] {error_message}")
            scan_progress_state["current_step"] = f"Error: {e}"
        finally:
            # Only delay if the scan wasn't cancelled, to allow immediate retry
            if not scan_cancel_event.is_set():
                time.sleep(10)
            scan_progress_state.update({"is_running": False, "current_step": "", "progress": 0, "scan_source": "", "scan_type": ""})
            if scanner_lock.locked():
                scanner_lock.release()

def run_lidarr_rename_scan():
    """
    Handles Lidarr integration. Can either trigger Lidarr's API directly
    or add 'rename' jobs to the local queue for a worker to process.
    Uses Lidarr API v1: https://lidarr.audio/docs/api/
    """
    with app.app_context():
        # Clear the cancel event first, before trying to acquire the lock
        scan_cancel_event.clear()
        
        # This function is now fully self-contained and runs in its own thread.
        if not scanner_lock.acquire(blocking=False):
            print(f"[{datetime.now()}] Lidarr rename scan trigger ignored: Another scan is already in progress.")
            # Reset the progress state since the API endpoint set it optimistically
            scan_progress_state.update({"is_running": False, "current_step": "Another scan is already in progress.", "progress": 0, "scan_source": "", "scan_type": ""})
            return

        scan_progress_state.update({"is_running": True, "current_step": "Initializing Lidarr rename scan...", "total_steps": 0, "progress": 0, "scan_source": "lidarr", "scan_type": "rename"})

        try:
            settings, db_error = get_worker_settings()
            if db_error:
                scan_progress_state["current_step"] = "Error: Database not available."
                return
    
            if settings.get('lidarr_enabled', {}).get('setting_value') != 'true':
                scan_progress_state["current_step"] = "Error: Lidarr integration is disabled."
                return
    
            host = settings.get('lidarr_host', {}).get('setting_value')
            api_key = settings.get('lidarr_api_key', {}).get('setting_value')
            send_to_queue = settings.get('lidarr_send_to_queue', {}).get('setting_value') == 'true'
    
            if not host or not api_key:
                scan_progress_state["current_step"] = "Error: Lidarr is not configured."
                return
    
            print(f"[{datetime.now()}] Lidarr Rename Scanner: Starting deep scan...")
            headers = {'X-Api-Key': api_key}
            base_url = host.rstrip('/')
            
            # Lidarr uses API v1, get all artists
            artists_res = requests.get(f"{base_url}/api/v1/artist", headers=headers, timeout=10, verify=get_arr_ssl_verify())
            artists_res.raise_for_status()
            all_artists = artists_res.json()
            
            scan_progress_state["total_steps"] = len(all_artists)
            conn = get_db()
            cur = conn.cursor()
            new_jobs_found = 0 
            renames_performed = 0 # Counter for direct renames
    
            for i, artist in enumerate(all_artists):
                if scan_cancel_event.is_set():
                    print("Lidarr rename scan cancelled by user.")
                    scan_progress_state["current_step"] = "Scan cancelled by user."
                    return
    
                artist_name = artist.get('artistName', 'Unknown Artist')
                scan_progress_state.update({"current_step": f"Analyzing: {artist_name}", "progress": i + 1})

                # Trigger a rescan for the artist, then check for rename results
                requests.post(f"{base_url}/api/v1/command", headers=headers, json={'name': 'RescanArtist', 'artistId': artist['id']}, timeout=10, verify=get_arr_ssl_verify())
                time.sleep(2) # Give Lidarr a moment to process before we query
                
                # Check for files that need renaming for this artist
                rename_res = requests.get(f"{base_url}/api/v1/rename?artistId={artist['id']}", headers=headers, timeout=10, verify=get_arr_ssl_verify())
                for rename_item in rename_res.json():
                    filepath = rename_item.get('existingPath')
                    if filepath:
                        # Determine job status or perform direct rename based on 'send_to_queue' setting
                        if send_to_queue:
                            job_status = 'awaiting_approval' # If selected, awaiting approval
                            metadata = {
                                'source': 'lidarr',
                                'artistName': artist['artistName'],
                                'artistId': artist.get('id'),
                                'trackFileId': rename_item.get('trackFileId'),
                                'albumId': rename_item.get('albumId')
                            }
                            cur.execute("INSERT INTO jobs (filepath, job_type, status, metadata) VALUES (%s, 'Rename Job', %s, %s) ON CONFLICT (filepath) DO NOTHING", (filepath, job_status, json.dumps(metadata)))
                            if cur.rowcount > 0: new_jobs_found += 1
                        else:
                            # Perform rename directly via Lidarr API
                            print(f"  -> Auto-renaming track file {filepath} via Lidarr API.")
                            payload = {"name": "RenameFiles", "artistId": artist['id'], "files": [rename_item.get('trackFileId')]}
                            rename_cmd_res = requests.post(f"{base_url}/api/v1/command", headers=headers, json=payload, timeout=20, verify=get_arr_ssl_verify())
                            rename_cmd_res.raise_for_status() 
                            renames_performed += 1
    
            conn.commit()
            if send_to_queue:
                message = f"Lidarr deep scan complete. Found {new_jobs_found} new files to rename. Added to queue for approval."
            else:
                message = f"Lidarr deep scan complete. Performed {renames_performed} automatic renames." 
            scan_progress_state["current_step"] = message
            print(f"[{datetime.now()}] {message}")

        except Exception as e:
            error_message = f"An error occurred during the Lidarr deep scan: {e}"
            print(f"[{datetime.now()}] {error_message}")
            scan_progress_state["current_step"] = f"Error: {e}"
        finally:
            # Only delay if the scan wasn't cancelled, to allow immediate retry
            if not scan_cancel_event.is_set():
                time.sleep(10)
            scan_progress_state.update({"is_running": False, "current_step": "", "progress": 0, "scan_source": "", "scan_type": ""})
            if scanner_lock.locked():
                scanner_lock.release()

def run_internal_scan(force_scan=False):
    """
    The core logic for scanning local directories.
    """
    with app.app_context():
        # Update progress state at the start
        scan_progress_state.update({"is_running": True, "current_step": "Initializing internal scan...", "total_steps": 0, "progress": 0, "scan_source": "internal", "scan_type": "media"})
        
        try:
            settings, db_error = get_worker_settings()
            if db_error:
                scan_progress_state.update({"current_step": "Error: Database not available."})
                return {"success": False, "message": "Database not available."}

            scan_paths_str = settings.get('internal_scan_paths', {}).get('setting_value', '')
            scan_paths = [path.strip() for path in scan_paths_str.split(',') if path.strip()]

            if not scan_paths:
                scan_progress_state.update({"current_step": "Error: No paths configured."})
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
            
            # Build list of codecs to skip based on settings
            # By default, we skip hevc/h265. If allow_hevc is true, we re-encode them.
            skip_codecs = []
            if settings.get('allow_hevc', {}).get('setting_value', 'false') != 'true':
                skip_codecs.extend(['hevc', 'h265'])
            if settings.get('allow_av1', {}).get('setting_value', 'false') != 'true':
                skip_codecs.append('av1')
            if settings.get('allow_vp9', {}).get('setting_value', 'false') != 'true':
                skip_codecs.append('vp9')

            new_files_found = 0
            valid_extensions = ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm')
            print(f"[{datetime.now()}] Internal Scanner: Starting scan of paths: {', '.join(scan_paths)}")

            # First pass: count total files to scan for progress tracking
            total_files = 0
            for folder in scan_paths:
                full_scan_path = os.path.join('/media', folder)
                for root, _, files in os.walk(full_scan_path):
                    for file in files:
                        if file.lower().endswith(valid_extensions):
                            total_files += 1
            
            scan_progress_state.update({"total_steps": total_files})
            files_processed = 0

            for folder in scan_paths:
                full_scan_path = os.path.join('/media', folder)
                print(f"[{datetime.now()}] Internal Scanner: Scanning '{full_scan_path}'...")
                scan_progress_state.update({"current_step": f"Scanning: {folder}"})
                
                for root, _, files in os.walk(full_scan_path):
                    for file in files:
                        if not file.lower().endswith(valid_extensions):
                            continue
                        
                        files_processed += 1
                        filepath = os.path.join(root, file)
                        scan_progress_state.update({"current_step": f"Checking: {file}", "progress": files_processed})
                        
                        if filepath in existing_jobs or filepath in encoded_history:
                            continue

                        try:
                            # Use ffprobe to get the video codec
                            ffprobe_cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", filepath]
                            codec = subprocess.check_output(ffprobe_cmd, text=True).strip().lower()
                            
                            print(f"  - Checking: {os.path.basename(filepath)} (Codec: {codec or 'N/A'})")
                            if codec and codec not in skip_codecs:
                                print(f"    -> Adding file to queue (codec: {codec}).")
                                cur.execute("INSERT INTO jobs (filepath, job_type, status) VALUES (%s, 'transcode', 'pending') ON CONFLICT (filepath) DO NOTHING", (filepath,))
                                if cur.rowcount > 0:
                                    new_files_found += 1
                        except (subprocess.CalledProcessError, FileNotFoundError) as e:
                            print(f"    -> Could not probe file '{filepath}'. Error: {e}")

            conn.commit()
            message = f"Scan complete. Added {new_files_found} new transcode jobs." if new_files_found > 0 else "Scan complete. No new files to add."
            scan_progress_state.update({"current_step": message})
            cur.close()
            return {"success": True, "message": message}
        finally:
            # Clear progress state after a brief delay to let UI catch the final message
            time.sleep(2)
            scan_progress_state.update({"is_running": False, "current_step": "", "progress": 0, "scan_source": "", "scan_type": ""})

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
            # Update progress state at the start
            scan_progress_state.update({"is_running": True, "current_step": "Initializing Plex scan...", "total_steps": 0, "progress": 0, "scan_source": "plex", "scan_type": "media"})
            
            settings, db_error = get_worker_settings()

            if db_error:
                scan_progress_state.update({"current_step": "Error: Database not available."})
                return {"success": False, "message": "Database not available."}

            plex_url = settings.get('plex_url', {}).get('setting_value')
            plex_token = settings.get('plex_token', {}).get('setting_value')
            plex_libraries_str = settings.get('plex_libraries', {}).get('setting_value', '')
            plex_libraries = [lib.strip() for lib in plex_libraries_str.split(',') if lib.strip()]

            if not all([plex_url, plex_token, plex_libraries]):
                scan_progress_state.update({"current_step": "Error: Plex not fully configured."})
                return {"success": False, "message": "Plex integration is not fully configured."}

            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            try:
                scan_progress_state.update({"current_step": "Connecting to Plex server..."})
                plex_server = PlexServer(plex_url, plex_token)
            except Exception as e:
                scan_progress_state.update({"current_step": f"Error: Could not connect to Plex."})
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
            
            # Build list of codecs to skip based on settings
            # By default, we skip hevc/h265. If allow_hevc is true, we re-encode them.
            skip_codecs = []
            if settings.get('allow_hevc', {}).get('setting_value', 'false') != 'true':
                skip_codecs.extend(['hevc', 'h265'])
            if settings.get('allow_av1', {}).get('setting_value', 'false') != 'true':
                skip_codecs.append('av1')
            if settings.get('allow_vp9', {}).get('setting_value', 'false') != 'true':
                skip_codecs.append('vp9')

            new_files_found = 0
            print(f"[{datetime.now()}] Plex Scanner: Starting scan of libraries: {', '.join(plex_libraries)}")
            
            # First pass: count total items for progress tracking
            total_items = 0
            for lib_name in plex_libraries:
                try:
                    library = plex_server.library.section(title=lib_name)
                    total_items += library.totalSize
                except Exception:
                    pass
            
            scan_progress_state.update({"total_steps": total_items})
            items_processed = 0
            
            for lib_name in plex_libraries:
                library = plex_server.library.section(title=lib_name)
                print(f"[{datetime.now()}] Plex Scanner: Scanning '{library.title}'...")
                scan_progress_state.update({"current_step": f"Scanning library: {library.title}"})
                
                for video in library.all():
                    items_processed += 1
                    
                    # Must reload to get all media part and stream details
                    video.reload()
                    
                    # Use the primary media object's codec for simplicity and reliability
                    if not hasattr(video, 'media') or not video.media:
                        continue

                    codec = video.media[0].videoCodec
                    filepath = video.media[0].parts[0].file
                    codec_lower = codec.lower() if codec else ''
                    
                    scan_progress_state.update({"current_step": f"Checking: {os.path.basename(filepath)}", "progress": items_processed})

                    print(f"  - Checking: {os.path.basename(filepath)} (Codec: {codec_lower or 'N/A'})")
                    if codec and codec_lower not in skip_codecs and filepath not in existing_jobs and filepath not in encoded_history:
                        print(f"    -> Adding file to queue (codec: {codec_lower}).")
                        cur.execute("INSERT INTO jobs (filepath, job_type, status) VALUES (%s, 'transcode', 'pending') ON CONFLICT (filepath) DO NOTHING", (filepath,))
                        if cur.rowcount > 0:
                            new_files_found += 1
            
            # Commit all the inserts at the end of the scan
            conn.commit()
            message = f"Scan complete. Added {new_files_found} new transcode jobs." if new_files_found > 0 else "Scan complete. No new files to add."
            scan_progress_state.update({"current_step": message})
            cur.close()
            return {"success": True, "message": message}
    finally:
        # Clear progress state after a brief delay to let UI catch the final message
        time.sleep(2)
        scan_progress_state.update({"is_running": False, "current_step": "", "progress": 0, "scan_source": "", "scan_type": ""})
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
        return jsonify(success=False, message="Another scan is already in progress."), 409
    
    # Immediately set the state to running to avoid a race condition with the frontend polling
    scan_progress_state.update({"is_running": True, "current_step": "Initializing rename scan...", "total_steps": 0, "progress": 0, "scan_source": "sonarr", "scan_type": "rename"})
    sonarr_rename_scan_event.set()
    return jsonify(success=True, message="Sonarr rename scan has been triggered.")

@app.route('/api/scan/quality', methods=['POST'])
def api_trigger_quality_scan():
    """API endpoint to manually trigger a Sonarr quality mismatch scan."""
    if scanner_lock.locked():
        return jsonify(success=False, message="Another scan is already in progress."), 409

    # Immediately set the state to running
    scan_progress_state.update({"is_running": True, "current_step": "Initializing quality scan...", "total_steps": 0, "progress": 0, "scan_source": "sonarr", "scan_type": "quality"})
    sonarr_quality_scan_event.set()
    return jsonify(success=True, message="Sonarr quality mismatch scan has been triggered.")

@app.route('/api/scan/radarr_rename', methods=['POST'])
def api_trigger_radarr_rename_scan():
    """API endpoint to manually trigger a Radarr rename scan or add jobs to queue."""
    if scanner_lock.locked():
        return jsonify(success=False, message="Another scan is already in progress."), 409
    
    # Immediately set the state to running to avoid a race condition with the frontend polling
    scan_progress_state.update({"is_running": True, "current_step": "Initializing Radarr rename scan...", "total_steps": 0, "progress": 0, "scan_source": "radarr", "scan_type": "rename"})
    radarr_rename_scan_event.set()
    return jsonify(success=True, message="Radarr rename scan has been triggered.")

@app.route('/api/scan/lidarr_rename', methods=['POST'])
def api_trigger_lidarr_rename_scan():
    """API endpoint to manually trigger a Lidarr rename scan or add jobs to queue."""
    if scanner_lock.locked():
        return jsonify(success=False, message="Another scan is already in progress."), 409
    
    # Immediately set the state to running to avoid a race condition with the frontend polling
    scan_progress_state.update({"is_running": True, "current_step": "Initializing Lidarr rename scan...", "total_steps": 0, "progress": 0, "scan_source": "lidarr", "scan_type": "rename"})
    lidarr_rename_scan_event.set()
    return jsonify(success=True, message="Lidarr rename scan has been triggered.")

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
def release_jobs():
    """Changes the status of cleanup or Rename jobs from 'awaiting_approval' to 'pending'."""
    data = request.get_json()
    job_ids = data.get('job_ids')
    release_all = data.get('release_all', False)
    job_type = data.get('job_type', 'cleanup')  # Default to cleanup for backwards compatibility

    # Allow both single job_type and list of job_types
    if isinstance(job_type, str):
        job_types = (job_type,)
    else:
        job_types = tuple(job_type)

    try:
        db = get_db()
        with db.cursor() as cur:
            if release_all:
                cur.execute("UPDATE jobs SET status = 'pending' WHERE job_type IN %s AND status = 'awaiting_approval'", (job_types,))
            elif job_ids:
                # The '%s' placeholder will be correctly formatted by psycopg2 for the IN clause
                cur.execute("UPDATE jobs SET status = 'pending' WHERE id IN %s AND job_type IN %s AND status = 'awaiting_approval'", (tuple(job_ids), job_types))
        db.commit()
        return jsonify(success=True, message="Selected jobs have been released to the queue.")
    except Exception as e:
        print(f"Error releasing jobs: {e}")
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
        response = requests.get(test_url, headers=headers, timeout=5, verify=get_arr_ssl_verify())

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

@app.route('/api/arr/stats', methods=['GET'])
def api_arr_stats():
    """
    Fetches statistics from Sonarr, Radarr, and Lidarr.
    Returns total counts for shows/seasons/episodes, movies, and artists/albums/tracks.
    
    Note: The *arr APIs don't have dedicated stats/summary endpoints, so we need to 
    fetch the full data lists and count them. This may be slow for very large libraries.
    """
    settings, db_error = get_worker_settings()
    if db_error:
        return jsonify(success=False, error=db_error), 500

    stats = {
        'sonarr': {'enabled': False, 'shows': 0, 'seasons': 0, 'episodes': 0},
        'radarr': {'enabled': False, 'movies': 0},
        'lidarr': {'enabled': False, 'artists': 0, 'albums': 0, 'tracks': 0}
    }

    # Sonarr stats
    if settings.get('sonarr_enabled', {}).get('setting_value') == 'true':
        host = settings.get('sonarr_host', {}).get('setting_value')
        api_key = settings.get('sonarr_api_key', {}).get('setting_value')
        
        if host and api_key:
            stats['sonarr']['enabled'] = True
            try:
                headers = {'X-Api-Key': api_key}
                base_url = host.rstrip('/')
                
                # Get series data - includes show and season counts
                # We sum the episodeCount from each series for the total episode count
                series_res = requests.get(f"{base_url}/api/v3/series", headers=headers, timeout=10, verify=get_arr_ssl_verify())
                series_res.raise_for_status()
                series_data = series_res.json()
                stats['sonarr']['shows'] = len(series_data)
                stats['sonarr']['seasons'] = sum(len(s.get('seasons', [])) for s in series_data)
                stats['sonarr']['episodes'] = sum(s.get('episodeCount', 0) for s in series_data)
            except Exception as e:
                print(f"Could not fetch Sonarr stats: {e}")

    # Radarr stats
    if settings.get('radarr_enabled', {}).get('setting_value') == 'true':
        host = settings.get('radarr_host', {}).get('setting_value')
        api_key = settings.get('radarr_api_key', {}).get('setting_value')
        
        if host and api_key:
            stats['radarr']['enabled'] = True
            try:
                headers = {'X-Api-Key': api_key}
                base_url = host.rstrip('/')
                
                # Get all movies
                movies_res = requests.get(f"{base_url}/api/v3/movie", headers=headers, timeout=10, verify=get_arr_ssl_verify())
                movies_res.raise_for_status()
                stats['radarr']['movies'] = len(movies_res.json())
            except Exception as e:
                print(f"Could not fetch Radarr stats: {e}")

    # Lidarr stats
    if settings.get('lidarr_enabled', {}).get('setting_value') == 'true':
        host = settings.get('lidarr_host', {}).get('setting_value')
        api_key = settings.get('lidarr_api_key', {}).get('setting_value')
        
        if host and api_key:
            stats['lidarr']['enabled'] = True
            try:
                headers = {'X-Api-Key': api_key}
                base_url = host.rstrip('/')
                
                # Get artist and album counts
                # For tracks, we sum the trackFileCount from albums instead of fetching all track files
                artists_res = requests.get(f"{base_url}/api/v1/artist", headers=headers, timeout=10, verify=get_arr_ssl_verify())
                artists_res.raise_for_status()
                stats['lidarr']['artists'] = len(artists_res.json())
                
                albums_res = requests.get(f"{base_url}/api/v1/album", headers=headers, timeout=10, verify=get_arr_ssl_verify())
                albums_res.raise_for_status()
                albums_data = albums_res.json()
                stats['lidarr']['albums'] = len(albums_data)
                
                # Sum up track counts from album statistics
                stats['lidarr']['tracks'] = sum(
                    a.get('statistics', {}).get('trackFileCount', 0) for a in albums_data
                )
            except Exception as e:
                print(f"Could not fetch Lidarr stats: {e}")

    return jsonify(success=True, stats=stats)

@app.route('/api/export', methods=['GET'])
def api_export_data():
    """Exports all settings, job queue, and history as a JSON file for backup purposes."""
    db = get_db()
    if db is None:
        return jsonify(error="Cannot connect to the PostgreSQL database."), 500
    
    export_data = {
        "export_version": 1,
        "exported_at": datetime.now().isoformat(),
        "dashboard_version": get_project_version(),
        "settings": {},
        "jobs": [],
        "encoded_files": [],
        "failed_files": [],
        "media_source_types": []
    }
    
    try:
        with db.cursor(cursor_factory=RealDictCursor) as cur:
            # Export settings
            cur.execute("SELECT setting_name, setting_value FROM worker_settings")
            for row in cur.fetchall():
                export_data["settings"][row['setting_name']] = row['setting_value']
            
            # Export jobs (pending and awaiting_approval only, not active encoding jobs)
            cur.execute("SELECT filepath, job_type, status, created_at, metadata FROM jobs WHERE status IN ('pending', 'awaiting_approval')")
            for row in cur.fetchall():
                job_entry = dict(row)
                job_entry['created_at'] = row['created_at'].isoformat() if row['created_at'] else None
                export_data["jobs"].append(job_entry)
            
            # Export encoded files history
            cur.execute("SELECT filename, original_size, new_size, encoded_by, encoded_at, status FROM encoded_files")
            for row in cur.fetchall():
                file_entry = dict(row)
                file_entry['encoded_at'] = row['encoded_at'].isoformat() if row['encoded_at'] else None
                export_data["encoded_files"].append(file_entry)
            
            # Export failed files
            cur.execute("SELECT filename, reason, failed_at FROM failed_files")
            for row in cur.fetchall():
                fail_entry = dict(row)
                fail_entry['failed_at'] = row['failed_at'].isoformat() if row['failed_at'] else None
                export_data["failed_files"].append(fail_entry)
            
            # Export media source types
            cur.execute("SELECT source_name, scanner_type, media_type, is_hidden FROM media_source_types")
            export_data["media_source_types"] = [dict(row) for row in cur.fetchall()]
        
        # Create the response with proper headers for file download
        response = app.response_class(
            response=json.dumps(export_data, indent=2),
            status=200,
            mimetype='application/json'
        )
        filename = f"librarrarian_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        print(f"Error exporting data: {e}")
        return jsonify(error=f"Export failed: {e}"), 500

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
        # This query now explicitly excludes internal job types that are not meant for workers.
        cur.execute("SELECT id, filepath, job_type FROM jobs WHERE status = 'pending' AND job_type NOT IN ('Rename Job', 'Quality Mismatch') ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED")
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

def trigger_arr_rescan_and_rename(filepath, settings):
    """
    Triggers a rescan in Sonarr/Radarr for the file's parent series/movie,
    then checks if a rename is needed. This is called after a transcode completes.
    Follows the renamarr pattern: rescan first to update mediainfo, then rename.
    """
    sonarr_enabled = settings.get('sonarr_enabled', {}).get('setting_value') == 'true'
    radarr_enabled = settings.get('radarr_enabled', {}).get('setting_value') == 'true'
    sonarr_auto_rename = settings.get('sonarr_auto_rename_after_transcode', {}).get('setting_value') == 'true'
    radarr_auto_rename = settings.get('radarr_auto_rename_after_transcode', {}).get('setting_value') == 'true'

    if not sonarr_enabled and not radarr_enabled:
        return
    
    # Try Sonarr first
    if sonarr_enabled and sonarr_auto_rename:
        host = settings.get('sonarr_host', {}).get('setting_value')
        api_key = settings.get('sonarr_api_key', {}).get('setting_value')
        
        if host and api_key:
            try:
                headers = {'X-Api-Key': api_key}
                base_url = host.rstrip('/')
                
                # Get all episode files to find the one matching our filepath
                episode_files_res = requests.get(f"{base_url}/api/v3/episodefile", headers=headers, timeout=10, verify=get_arr_ssl_verify())
                episode_files_res.raise_for_status()
                
                for ep_file in episode_files_res.json():
                    if ep_file.get('path') == filepath:
                        series_id = ep_file.get('seriesId')
                        episode_file_id = ep_file.get('id')
                        
                        print(f"[{datetime.now()}] Found file in Sonarr. Series ID: {series_id}, File ID: {episode_file_id}")
                        
                        # Step 1: Trigger a rescan to update the mediainfo
                        print(f"[{datetime.now()}] Triggering Sonarr RescanSeries for series {series_id}")
                        rescan_payload = {'name': 'RescanSeries', 'seriesId': series_id}
                        requests.post(f"{base_url}/api/v3/command", headers=headers, json=rescan_payload, timeout=10, verify=get_arr_ssl_verify())
                        
                        # Give Sonarr time to rescan
                        time.sleep(3)
                        
                        # Step 2: Check if rename is needed
                        rename_res = requests.get(f"{base_url}/api/v3/rename?seriesId={series_id}", headers=headers, timeout=10, verify=get_arr_ssl_verify())
                        rename_res.raise_for_status()
                        
                        for rename_item in rename_res.json():
                            if rename_item.get('episodeFileId') == episode_file_id:
                                # Step 3: Trigger rename
                                print(f"[{datetime.now()}] Triggering Sonarr rename for file {episode_file_id}")
                                rename_payload = {"name": "RenameFiles", "seriesId": series_id, "files": [episode_file_id]}
                                requests.post(f"{base_url}/api/v3/command", headers=headers, json=rename_payload, timeout=20, verify=get_arr_ssl_verify())
                                print(f"[{datetime.now()}] Sonarr auto-rename triggered successfully.")
                                break
                        break
            except Exception as e:
                print(f"⚠️ Could not trigger Sonarr rescan/rename: {e}")

    # Try Radarr if enabled
    if radarr_enabled and radarr_auto_rename:
        host = settings.get('radarr_host', {}).get('setting_value')
        api_key = settings.get('radarr_api_key', {}).get('setting_value')
        
        if host and api_key:
            try:
                headers = {'X-Api-Key': api_key}
                base_url = host.rstrip('/')
                
                # Get all movies to find the one matching our filepath
                movies_res = requests.get(f"{base_url}/api/v3/movie", headers=headers, timeout=10, verify=get_arr_ssl_verify())
                movies_res.raise_for_status()
                
                for movie in movies_res.json():
                    movie_file = movie.get('movieFile')
                    if movie_file and movie_file.get('path') == filepath:
                        movie_id = movie.get('id')
                        movie_file_id = movie_file.get('id')
                        
                        print(f"[{datetime.now()}] Found file in Radarr. Movie ID: {movie_id}, File ID: {movie_file_id}")
                        
                        # Step 1: Trigger a rescan to update the mediainfo
                        print(f"[{datetime.now()}] Triggering Radarr RescanMovie for movie {movie_id}")
                        rescan_payload = {'name': 'RescanMovie', 'movieId': movie_id}
                        requests.post(f"{base_url}/api/v3/command", headers=headers, json=rescan_payload, timeout=10, verify=get_arr_ssl_verify())
                        
                        # Give Radarr time to rescan
                        time.sleep(3)
                        
                        # Step 2: Check if rename is needed
                        rename_res = requests.get(f"{base_url}/api/v3/rename?movieId={movie_id}", headers=headers, timeout=10, verify=get_arr_ssl_verify())
                        rename_res.raise_for_status()
                        
                        for rename_item in rename_res.json():
                            if rename_item.get('movieFileId') == movie_file_id:
                                # Step 3: Trigger rename
                                print(f"[{datetime.now()}] Triggering Radarr rename for file {movie_file_id}")
                                rename_payload = {"name": "RenameFiles", "movieId": movie_id, "files": [movie_file_id]}
                                requests.post(f"{base_url}/api/v3/command", headers=headers, json=rename_payload, timeout=20, verify=get_arr_ssl_verify())
                                print(f"[{datetime.now()}] Radarr auto-rename triggered successfully.")
                                break
                        break
            except Exception as e:
                print(f"⚠️ Could not trigger Radarr rescan/rename: {e}")

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
                    print(f"[{datetime.now()}] Post-transcode: Triggering Plex library update to recognize newly encoded file.")
                    plex.library.update()
            except Exception as e:
                print(f"⚠️ Could not trigger Plex scan: {e}")

            # Trigger Sonarr/Radarr rescan and auto-rename if enabled
            try:
                settings, _ = get_worker_settings()
                trigger_arr_rescan_and_rename(job['filepath'], settings)
            except Exception as e:
                print(f"⚠️ Could not trigger Arr rescan/rename: {e}")

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
        cur.execute("UPDATE jobs SET status = 'failed', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (job_id,))
        message = f"Job {job_id} ({job['job_type']}) failed and logged."

    conn.commit()
    cur.close()
    return jsonify({"message": message})


# --- Background Threads ---

def plex_scanner_thread():
    """Scans Plex libraries and adds non-HEVC files to the jobs table."""
    # This thread now waits for the db_ready_event before starting its loop.
    db_ready_event.wait()
    print("Plex Scanner thread is now active.")

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
    # This thread now waits for the db_ready_event before starting its loop.
    db_ready_event.wait()
    print("Cleanup Scanner thread is now active.")
    while True:

        # Wait indefinitely until the event is set
        cleanup_scan_now_event.wait()
        print(f"[{datetime.now()}] Manual cleanup scan trigger received.")
        cleanup_scan_now_event.clear() # Reset the event
        run_cleanup_scan()

def arr_job_processor_thread():
    """
    This background thread periodically checks for and processes internal jobs
    that are not meant for workers, such as Sonarr/Radarr/Lidarr rename commands.
    """
    # This thread now waits for the db_ready_event before starting its loop.
    db_ready_event.wait()
    print("Arr Job Processor thread is now active.")

    while True:
        try:
            with app.app_context():
                conn = get_db()
                if not conn:
                    time.sleep(60) # Wait and retry if DB is down
                    continue

                cur = conn.cursor(cursor_factory=RealDictCursor)
                settings, _ = get_worker_settings()
                
                # Use FOR UPDATE SKIP LOCKED to ensure multiple dashboard replicas don't grab the same job.
                cur.execute("SELECT * FROM jobs WHERE job_type = 'Rename Job' AND status = 'pending' LIMIT 10 FOR UPDATE SKIP LOCKED")
                jobs_to_process = cur.fetchall()
                
                if jobs_to_process:
                    print(f"Found {len(jobs_to_process)} rename jobs to process.")
                    
                    for job in jobs_to_process:
                        metadata = job.get('metadata', {})
                        source = metadata.get('source', 'sonarr')  # Default to sonarr for backwards compatibility
                        
                        if source == 'radarr':
                            # Process Radarr rename job
                            host = settings.get('radarr_host', {}).get('setting_value')
                            api_key = settings.get('radarr_api_key', {}).get('setting_value')
                            
                            if not host or not api_key:
                                print(f"Radarr is not configured. Skipping job {job['id']}.")
                                continue
                            
                            file_id = metadata.get('movieFileId')
                            movie_id = metadata.get('movieId')

                            if not file_id or not movie_id:
                                print(f"Failing job {job['id']}: Missing 'movieFileId' or 'movieId' in metadata.")
                                cur.execute("UPDATE jobs SET status = 'failed', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (job['id'],))
                                continue
                            
                            try:
                                base_url = host.rstrip('/')
                                headers = {'X-Api-Key': api_key}
                                print(f"Processing Radarr rename for job {job['id']} (File ID: {file_id})")
                                payload = {"name": "RenameFiles", "movieId": movie_id, "files": [file_id]}
                                res = requests.post(f"{base_url}/api/v3/command", headers=headers, json=payload, timeout=20, verify=get_arr_ssl_verify())
                                res.raise_for_status()
                                
                                # Mark job as completed
                                print(f"Radarr rename job {job['id']} completed successfully.")
                                cur.execute("UPDATE jobs SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (job['id'],))

                            except requests.exceptions.RequestException as e:
                                print(f"Error processing Radarr rename job {job['id']}: {e}")
                                cur.execute("UPDATE jobs SET status = 'failed', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (job['id'],))
                        
                        elif source == 'lidarr':
                            # Process Lidarr rename job
                            host = settings.get('lidarr_host', {}).get('setting_value')
                            api_key = settings.get('lidarr_api_key', {}).get('setting_value')
                            
                            if not host or not api_key:
                                print(f"Lidarr is not configured. Skipping job {job['id']}.")
                                continue
                            
                            file_id = metadata.get('trackFileId')
                            artist_id = metadata.get('artistId')

                            if not file_id or not artist_id:
                                print(f"Failing job {job['id']}: Missing 'trackFileId' or 'artistId' in metadata.")
                                cur.execute("UPDATE jobs SET status = 'failed', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (job['id'],))
                                continue
                            
                            try:
                                base_url = host.rstrip('/')
                                headers = {'X-Api-Key': api_key}
                                print(f"Processing Lidarr rename for job {job['id']} (File ID: {file_id})")
                                # Lidarr uses API v1
                                payload = {"name": "RenameFiles", "artistId": artist_id, "files": [file_id]}
                                res = requests.post(f"{base_url}/api/v1/command", headers=headers, json=payload, timeout=20, verify=get_arr_ssl_verify())
                                res.raise_for_status()
                                
                                # Mark job as completed
                                print(f"Lidarr rename job {job['id']} completed successfully.")
                                cur.execute("UPDATE jobs SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (job['id'],))

                            except requests.exceptions.RequestException as e:
                                print(f"Error processing Lidarr rename job {job['id']}: {e}")
                                cur.execute("UPDATE jobs SET status = 'failed', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (job['id'],))
                        
                        else:
                            # Process Sonarr rename job (default)
                            host = settings.get('sonarr_host', {}).get('setting_value')
                            api_key = settings.get('sonarr_api_key', {}).get('setting_value')
                            
                            if not host or not api_key:
                                print(f"Sonarr is not configured. Skipping job {job['id']}.")
                                continue

                            file_id = metadata.get('episodeFileId')
                            series_id = metadata.get('seriesId')

                            if not file_id or not series_id:
                                print(f"Failing job {job['id']}: Missing 'episodeFileId' or 'seriesId' in metadata.")
                                cur.execute("UPDATE jobs SET status = 'failed', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (job['id'],))
                                continue
                            
                            try:
                                base_url = host.rstrip('/')
                                headers = {'X-Api-Key': api_key}
                                print(f"Processing Sonarr rename for job {job['id']} (File ID: {file_id})")
                                payload = {"name": "RenameFiles", "seriesId": series_id, "files": [file_id]}
                                res = requests.post(f"{base_url}/api/v3/command", headers=headers, json=payload, timeout=20, verify=get_arr_ssl_verify())
                                res.raise_for_status()
                                
                                # Mark job as completed
                                print(f"Sonarr rename job {job['id']} completed successfully.")
                                cur.execute("UPDATE jobs SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (job['id'],))

                            except requests.exceptions.RequestException as e:
                                print(f"Error processing Sonarr rename job {job['id']}: {e}")
                                cur.execute("UPDATE jobs SET status = 'failed', updated_at = CURRENT_TIMESTAMP WHERE id = %s", (job['id'],))
                
                conn.commit()
                cur.close()

        except Exception as e:
            print(f"CRITICAL ERROR in arr_job_processor_thread: {e}")
            # Avoid a tight loop on critical error
            time.sleep(300)
        
        # Wait 60 seconds before checking for new internal jobs
        time.sleep(60)

def perform_database_backup():
    """
    Performs a database backup. Can be called manually or from scheduled thread.
    Returns a tuple: (success: bool, message: str, backup_file: str or None)
    """
    try:
        # Get retention settings
        settings, _ = get_worker_settings()
        
        # Safely parse retention days with validation
        try:
            retention_days = int(settings.get('backup_retention_days', {}).get('setting_value', '7'))
            # Ensure retention is within reasonable bounds
            if retention_days < 1:
                retention_days = 1
            elif retention_days > 365:
                retention_days = 365
        except (ValueError, TypeError):
            print(f"[{datetime.now()}] Warning: Invalid backup_retention_days value, using default of 7")
            retention_days = 7
        
        # Database backups are stored in a fixed location, not the user-configurable backup_directory
        backup_dir = '/data/backup'
        
        # Create backup directory if it doesn't exist
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generate backup filename with new format: YYYYMMDD.HHMMSS.tar.gz
        timestamp = datetime.now().strftime('%Y%m%d.%H%M%S')
        backup_file = os.path.join(backup_dir, f'{timestamp}.tar.gz')
        
        print(f"[{datetime.now()}] Starting database backup to: {backup_file}")
        
        # Use pg_dump to create backup
        # Get database credentials from environment
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = os.environ.get('DB_PORT', '5432')
        db_name = os.environ.get('DB_NAME', 'librarrarian')
        db_user = os.environ.get('DB_USER', 'transcode')
        db_password = os.environ.get('DB_PASSWORD', '')
        
        # Set PGPASSWORD environment variable for pg_dump
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password
        
        # Run pg_dump and pipe through gzip (note: .tar.gz extension for consistency, but this is a gzipped SQL dump)
        pg_dump_cmd = [
            'pg_dump',
            '-h', db_host,
            '-p', db_port,
            '-U', db_user,
            '-d', db_name,
            '--no-password'
        ]
        
        # Execute pg_dump and gzip
        with open(backup_file, 'wb') as f:
            pg_dump_process = subprocess.Popen(
                pg_dump_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            gzip_process = subprocess.Popen(
                ['gzip'],
                stdin=pg_dump_process.stdout,
                stdout=f,
                stderr=subprocess.PIPE
            )
            
            pg_dump_process.stdout.close()
            gzip_stderr = gzip_process.communicate()[1]
            pg_dump_process.wait()  # Wait for pg_dump to finish
            pg_dump_stderr = pg_dump_process.stderr.read()
            
            # Check both processes for errors
            if pg_dump_process.returncode != 0:
                error_msg = f"Database backup failed: pg_dump returned {pg_dump_process.returncode}"
                if pg_dump_stderr:
                    error_msg += f" - {pg_dump_stderr.decode()}"
                print(f"[{datetime.now()}] {error_msg}")
                # Remove incomplete backup file
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                return (False, error_msg, None)
            
            if gzip_process.returncode == 0:
                # Get file size for log
                file_size = os.path.getsize(backup_file)
                file_size_mb = file_size / (1024 * 1024)
                message = f"Database backup completed successfully. Size: {file_size_mb:.2f} MB"
                print(f"[{datetime.now()}] {message}")
                
                # Clean up old backups based on retention policy
                # Include both new (.tar.gz) and old (.sql.gz) formats during transition
                if os.path.exists(backup_dir):
                    backup_files = [f for f in os.listdir(backup_dir) 
                                    if f.endswith('.tar.gz') or (f.startswith('librarrarian_backup_') and f.endswith('.sql.gz'))]
                    backup_files.sort(reverse=True)
                    
                    # Keep only the most recent backups based on retention setting
                    for old_backup in backup_files[retention_days:]:
                        old_backup_path = os.path.join(backup_dir, old_backup)
                        try:
                            os.remove(old_backup_path)
                            print(f"[{datetime.now()}] Removed old backup: {old_backup}")
                        except Exception as e:
                            print(f"[{datetime.now()}] Failed to remove old backup {old_backup}: {e}")
                
                return (True, message, backup_file)
            else:
                error_msg = f"Database backup failed: gzip returned {gzip_process.returncode}"
                if gzip_stderr:
                    error_msg += f" - {gzip_stderr.decode()}"
                print(f"[{datetime.now()}] {error_msg}")
                # Remove incomplete backup file
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                return (False, error_msg, None)
        
    except Exception as e:
        error_msg = f"Error performing database backup: {e}"
        print(f"[{datetime.now()}] {error_msg}")
        return (False, error_msg, None)

def database_backup_thread():
    """
    This background thread performs daily database backups at the configured time.
    Backups are created as PostgreSQL dumps with timestamps.
    """
    db_ready_event.wait()
    print("Database backup thread is now active.")
    
    while True:
        try:
            with app.app_context():
                # Get backup settings
                settings, _ = get_worker_settings()
                backup_enabled = settings.get('backup_enabled', {}).get('setting_value', 'true') == 'true'
                backup_time_str = settings.get('backup_time', {}).get('setting_value', '02:00')
                
                # Parse the backup time (HH:MM format)
                try:
                    backup_hour, backup_minute = map(int, backup_time_str.split(':'))
                except:
                    backup_hour, backup_minute = 2, 0  # Default to 2:00 AM
                
                # Calculate time until next backup
                now = datetime.now()
                next_backup = now.replace(hour=backup_hour, minute=backup_minute, second=0, microsecond=0)
                
                # If the backup time has already passed today, schedule for tomorrow
                if next_backup <= now:
                    next_backup += timedelta(days=1)
                
                # Calculate seconds to wait
                seconds_to_wait = (next_backup - now).total_seconds()
                
                if backup_enabled:
                    print(f"[{datetime.now()}] Next database backup scheduled for: {next_backup}")
                else:
                    print(f"[{datetime.now()}] Database backups are disabled. Next check at: {next_backup}")
            
            # Wait until backup time (outside app context to avoid holding resources)
            time.sleep(seconds_to_wait)
            
            # Perform the backup within app context only if enabled
            with app.app_context():
                settings, _ = get_worker_settings()
                backup_enabled = settings.get('backup_enabled', {}).get('setting_value', 'true') == 'true'
                if backup_enabled:
                    perform_database_backup()
                else:
                    print(f"[{datetime.now()}] Skipping backup - backups are disabled")
            
        except Exception as e:
            print(f"[{datetime.now()}] Error in database_backup_thread: {e}")
            # Continue running even if backup fails
            time.sleep(3600)  # Wait 1 hour before retrying on error

# Start the background threads when the app is initialized by Gunicorn.
scanner_thread = threading.Thread(target=plex_scanner_thread, daemon=True)
scanner_thread.start()
arr_background_scanner = threading.Thread(target=arr_background_thread, daemon=True)
arr_background_scanner.start()
cleanup_thread = threading.Thread(target=cleanup_scanner_thread, daemon=True)
cleanup_thread.start()
arr_job_processor = threading.Thread(target=arr_job_processor_thread, daemon=True)
arr_job_processor.start()
backup_thread = threading.Thread(target=database_backup_thread, daemon=True)
backup_thread.start()

if __name__ == '__main__':
    # For local development, run migrations then start the app
    initialize_database_if_needed()
    run_migrations()
    db_ready_event.set() # Signal to all threads that the DB is ready
    # Use host='0.0.0.0' to make the app accessible on your network
    # WARNING: debug=True should NEVER be used in production. In production,
    # the app is run with Gunicorn which doesn't use Flask's debug mode.
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # When run by Gunicorn in production, run migrations first, then signal ready.
    # Gunicorn will then start the Flask app.
    initialize_database_if_needed()
    run_migrations()
    db_ready_event.set()
