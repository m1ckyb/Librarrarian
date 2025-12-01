# Gemini Code Assist - Project Memory for Librarrarian

This document is a summary of the key architectural patterns, decisions, and common pitfalls encountered during the development of the Librarrarian project. It serves as a "memory" to ensure future work is consistent and efficient.


## Project File Structure

This is a reference list of the key files in the project and their purpose.

```
# High-Level Documentation
README.md              # Main project overview, features, and deployment instructions.
summary.md             # A concise, high-level summary of the project's architecture and purpose.
remember.md            # This file. My memory of architectural patterns, workflows, and common pitfalls.

# Versioning & Release Management
VERSION.txt            # Single source of truth for the entire project's version number.
CHANGELOG.md           # A log of all changes for each released version.
unreleased.md          # A staging area for documenting changes before they are part of a release.

# Docker & Deployment
docker-compose.yml     # Defines and orchestrates the production services (dashboard, worker, db).
docker-compose-dev.yml # A version of the compose file for local development, using local builds.
.env.example           # An example environment file showing required variables.

# Dashboard Application (The Brain)
dashboard/Dockerfile         # Instructions for building the dashboard Docker image.
dashboard/dashboard_app.py   # The main Flask application: serves the UI, provides the API, and runs background threads.
dashboard/static/js/app.js   # Core frontend JavaScript for UI interactivity, API calls, and dynamic updates.
dashboard/templates/         # Directory containing all Jinja2 HTML templates for the UI.

# Worker Application (The Muscle)
worker/Dockerfile            # Instructions for building the worker Docker image.
worker/transcode.py          # The main script for the worker node. It requests jobs and performs transcodes.

# CI/CD Pipelines
.github/workflows/     # Directory for GitHub Actions workflows (e.g., for Docker image publishing).
.forgejo/workflows/    # Directory for Forgejo Actions, a parallel CI/CD pipeline for self-hosting.
```

## Session Initialization

When a new chat session begins, I must first read the following files to establish a complete understanding of the project's current state, architecture, and purpose:

1.  `remember.md` (for architectural principles and workflows)
2.  `README.md` (for project overview and deployment instructions)
3.  `summary.md` (for a high-level feature summary)
4.  `CHANGELOG.md` (for recent changes and version history)
5.  `unreleased.md` (for upcoming changes and known bugs)

This ensures all subsequent responses are informed by the full project context.

---

## Guiding Principles

1.  **Security First**: All new features must be designed with security in mind. This includes protecting user-facing pages with session-based authentication and securing machine-to-machine API endpoints with API keys.
2.  **Clear Data Contracts**: The data structure sent by a backend API endpoint (the "contract") must exactly match what the frontend JavaScript expects. Any changes to one must be reflected in the other to prevent "undefined" errors in the UI.
3.  **Configuration Management**:
    *   **Secrets & Deployment Config** (e.g., database passwords, API keys, OIDC details) belong in environment variables (`.env` file).
    *   **Documentation**: Whenever an environment variable is added or changed, `.env.example` **must** be updated to reflect the change with placeholder data and a descriptive comment.
    *   **User-Tunable Settings** (e.g., quality values, scan delays, feature flags) belong in the `worker_settings` database table and should be managed via the UI.

---
## Development Workflow

1.  **Continuous Documentation**: After every feature addition, change, or bug fix, `unreleased.md` **must** be updated immediately with a concise summary of the change under the appropriate heading (`### Added`, `### Changed`, `### Fixed`). This ensures the changelog is always ready for the next release.
    *   **Exception**: Changes made to this file (`remember.md`) do not need to be documented in `unreleased.md`.

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

## 5. Database Migrations

**Problem:** When the database schema needs to be changed (e.g., adding a new column or setting), existing users would have to either manually run SQL commands or completely reset their database, causing data loss.

**Correct Pattern:** An automatic migration system that runs on application startup.

1.  **Schema Versioning:** The database contains a `schema_version` table that holds a single integer representing the current version of the schema.
2.  **Target Version:** The `dashboard_app.py` file defines a `TARGET_SCHEMA_VERSION` constant, which is the version the code expects.
3.  **Migration Dictionary:** A `MIGRATIONS` dictionary in `dashboard_app.py` maps version numbers to a list of SQL commands required to upgrade to that version.
4.  **Startup Check:** On startup, the `run_migrations()` function compares the database's version to the target version. If the database is outdated, it applies all necessary migrations in sequential order, updating the schema version after each step.

**How to Add a New Migration:**

1.  **Increment Target Version:** In `dashboard_app.py`, increase the `TARGET_SCHEMA_VERSION` constant by 1 (e.g., from `3` to `4`).
2.  **Add Migration SQL:** Add a new entry to the `MIGRATIONS` dictionary. The key should be the new version number. The value should be a list of SQL strings.
3.  **Write Idempotent SQL:** The SQL commands **must** be idempotent, meaning they can be run multiple times without causing errors. Use clauses like `ADD COLUMN IF NOT EXISTS` and `INSERT ... ON CONFLICT DO NOTHING`.

**Example (`dashboard_app.py`):**
```python
TARGET_SCHEMA_VERSION = 4
MIGRATIONS = {
    # ... existing migrations ...
    4: [
        "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS new_feature_flag BOOLEAN DEFAULT false;",
        "INSERT INTO worker_settings (setting_name, setting_value) VALUES ('new_setting', 'default_value') ON CONFLICT (setting_name) DO NOTHING;"
    ]
}
```

## 3. Authentication & Authorization

**Problem:** The cluster has two types of clients: human users (via browser) and machine clients (workers). A single auth system can cause conflicts.

**Correct Pattern:** A multi-layered approach.

1.  **User Authentication (OIDC / Local):** Handled by the Flask session (`'user' in session`). The `require_login` function protects all UI-facing routes.
2.  **Worker Authentication (API Key):** All API routes (`/api/*`) **must** be protected. The `require_login` function must check for a valid `X-API-Key` in the request headers. The worker script **must** send this header with every API call if `AUTH_ENABLED` is true.
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

---

### Release Process

When requested to **"Make a <type> release"**, where `<type>` is `Patch`, `Minor`, or `Major`, the following steps must be performed based on Semantic Versioning:

1.  **Determine New Version**: Read the current version from `VERSION.txt` (e.g., `X.Y.Z`).
    *   For a **Patch** release, the new version will be `X.Y.(Z+1)`.
    *   For a **Minor** release, the new version will be `X.(Y+1).0`.
    *   For a **Major** release, the new version will be `(X+1).0.0`.

2.  **Update `CHANGELOG.md`**:
    *   Create a new version heading with the new version number and current date (e.g., `## [1.0.0] - YYYY-MM-DD - Release Name`).
    *   Move all content from `unreleased.md` into this new section.
    *   Ensure the formatting is correct and consistent with previous entries.
    *   **Do not** add an `[Unreleased]` section back to the top of `CHANGELOG.md`. This file should only contain released versions.

3.  **Clear `unreleased.md`**: After moving the content, reset `unreleased.md` to its default empty state, ready for the next development cycle.

4.  **Update `VERSION.txt`**: Change the content of `VERSION.txt` to the new version number.

5.  **Update `docker-compose.yml`**: Update the `image` tags for the `dashboard` and `worker` services to the new version number.

6.  **Update `README.md` and `summary.md`**: Review both files to see if any of the new features or significant changes from the changelog need to be reflected in the project overview or feature list. Update them as necessary.

---

## Technical Debt & Future Improvements

---

## Agent Capabilities & Limitations

*   **Shell Access**: I do not have direct access to the user's shell. I cannot run commands like `docker-compose`, `git`, or other command-line tools myself. I must always ask the user to run these commands and provide the output if needed.
*   **File System Access**: I have full read and write access to all files within this project repository. I will make necessary changes directly without asking for permission, as per standing instructions.