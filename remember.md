# Gemini Code Assist - Project Memory for CodecShift

This document is a summary of the key architectural patterns, decisions, and common pitfalls encountered during the development of the CodecShift project. It serves as a "memory" to ensure future work is consistent and efficient.

---

## 1. Asynchronous Tasks & Background Threads

**Problem:** Long-running operations (like scanning media libraries) triggered via a web request cause Gunicorn `WORKER TIMEOUT` errors.

**Correct Pattern:** All potentially long-running tasks initiated from the dashboard UI must be asynchronous.

1.  **API Endpoint (The Trigger):** The Flask route (e.g., `/api/plex/scan`) must be non-blocking. Its only job is to set a `threading.Event` and return an immediate `jsonify` response to the UI. It should **never** perform the long task itself.
2.  **Background Thread (The Doer):** A dedicated background thread, started when the application initializes, runs in an infinite loop (`while True:`).
3.  **Event & Lock:** The thread waits on the `threading.Event` (e.g., `scan_now_event.wait()`). When the event is set by the API, the thread wakes up, acquires a `threading.Lock` to prevent concurrent runs, performs the long task (e.g., `os.walk`, Plex library scan), and finally releases the lock.

**Example Files:** `dashboard/dashboard_app.py` (see `plex_scanner_thread` and `cleanup_scanner_thread`).

---

## 2. Database Initialization & Startup

**Problem:** On a fresh deployment, the `dashboard` and `worker` services start before the `db` container is ready and the schema is created. This causes `relation "..." does not exist` and `permission denied` errors.

**Correct Pattern:** Use Docker's built-in Postgres initialization mechanism.

1.  **`init.sql`:** A single `init.sql` file in the project root contains all `CREATE TABLE IF NOT EXISTS ...` statements.
2.  **Permissions are CRITICAL:** After each `CREATE TABLE` statement, permissions **must** be granted to the application user (`transcode`). Example:
    ```sql
    GRANT ALL PRIVILEGES ON TABLE nodes TO transcode;
    GRANT USAGE, SELECT ON SEQUENCE nodes_id_seq TO transcode;
    ```
3.  **Default Settings:** The `init.sql` script **must** populate the `worker_settings` table with a complete set of default values. This prevents the dashboard's API from failing on a fresh start.
4.  **`docker-compose.yml` Orchestration:**
    *   The `db` service uses a `healthcheck` to report when it's ready.
    *   The `init.sql` file is mounted into `/docker-entrypoint-initdb.d/init.sql` on the `db` service.
    *   The `dashboard` and `worker` services have a `depends_on` condition for the `db` service to be `service_healthy`.

---

## 3. Authentication & Authorization

**Problem:** The cluster has two types of clients: human users (via browser) and machine clients (workers). A single auth system can cause conflicts.

**Correct Pattern:** A multi-layered approach.

1.  **User Authentication (OIDC / Local):** Handled by the Flask session (`'user' in session`). The `require_login` function protects all UI-facing routes.
2.  **Worker Authentication (API Key):** All API routes (`/api/*`) are protected. The `require_login` function checks for a valid `X-API-Key` in the request headers. The worker script **must** send this header with every API call if `AUTH_ENABLED` is true.
3.  **OIDC Gotchas:** Remember the series of fixes for OIDC:
    *   `ProxyFix` middleware is required when behind a reverse proxy.
    *   Explicitly list supported signing algorithms (`id_token_signing_alg_values_supported`).
    *   Allow SSL verification to be disabled for development environments (`OIDC_SSL_VERIFY`).

---

## 4. Versioning & Build Process

**Problem:** Inconsistent versioning and Docker build contexts between local `docker-compose` and GitHub Actions CI/CD.

**Correct Pattern:**

1.  **Single Source of Truth:** `VERSION.txt` in the project root is the master version.
2.  **Consistent Build Context:** All `Dockerfile`s and CI/CD build steps **must** use the project root (`.`) as the build context.
3.  **Correct `COPY` Paths:** Inside a `Dockerfile`, all `COPY` commands must use paths relative to the project root (e.g., `COPY dashboard/requirements.txt .`).
4.  **Dynamic Version Reading:** Both the dashboard and worker applications read their version at runtime from the `VERSION.txt` file copied into their respective images. The dashboard footer and worker startup logs must display this dynamic version.
5.  **Server-Side Mismatch Detection:** The dashboard is the source of truth for version mismatches. The `/api/status` endpoint compares its own version with the version reported by each worker and flags any discrepancies.
