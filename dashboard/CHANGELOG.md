# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2025-11-23 - The Great Refactor: Centralized Job Management

### Added
- **Job Queue System**: Introduced a centralized job queue managed by the dashboard. Workers now request jobs from the dashboard via a new API.
- **Plex Integration**:
  - Added in-app Plex account linking via username/password authentication.
  - Plex server URL, authentication token, and monitored libraries are now configured in the UI and stored in the database.
  - The dashboard now scans selected Plex libraries to automatically populate the transcode job queue.
- **UI Enhancements**:
  - New "Job Queue" tab to view pending, assigned, and failed jobs.
  - New "Cleanup" tab to create jobs for removing stale temporary files left by workers.
  - The UI now deep-links to specific tabs using URL hashes (e.g., `/#options-tab-pane`).
- **Database Initialization**: A new `init_db.py` script ensures the database is initialized before the application starts, improving reliability in Docker.

### Changed
- **Core Architecture**:
  - **Dashboard**: Is now the central "brain" of the cluster. It scans Plex for media, manages the job queue, and assigns work.
  - **Workers**: Are now "dumb" clients. They no longer scan the filesystem and instead request jobs directly from the dashboard's API.
- **Plex Authentication**: Replaced the previous PIN-based OAuth flow with a simpler and more robust username/password modal form.
- **Configuration**: Removed reliance on environment variables for Plex setup. All Plex-related settings are now managed dynamically through the web UI.
- **UI/Frontend**:
  - Replaced page redirects with direct template rendering after form submissions on the Options page to prevent race conditions and ensure the UI shows the latest data.
  - Consolidated and refactored all page JavaScript into a single, organized `DOMContentLoaded` event listener for improved reliability and maintainability.
  - The "Active Nodes" tab is no longer the default, allowing for better deep-linking.
- **Database**:
  - Implemented `INSERT ... ON CONFLICT` for updating `worker_settings`, making the process more robust for new database setups.
  - The database initialization logic is now separated from the main application runtime.

### Fixed
- **Background Scanner**: The Plex scanner thread is now started correctly when the application is run with a WSGI server like Gunicorn, ensuring it runs in a production Docker environment.
- **Database Queries**: Corrected SQL queries to use `last_heartbeat` for node activity checks and ensured all database operations target the correct tables.
- **Plex API Calls**:
  - Added required client identification headers to all Plex API requests to ensure compatibility.
  - Corrected the instantiation of the `PlexServer` and login clients to align with the latest `plexapi` library standards.
- **UI Bugs**:
  - Resolved a race condition where Plex libraries would fail to load on the Options page immediately after saving the server URL.
  - Fixed an issue where the Plex login form would not submit correctly.

### Removed
- **Plex Environment Variables**: The system no longer uses environment variables for Plex configuration (`PLEX_URL`, `PLEX_TOKEN`, etc.).
- **Filesystem Scanning from Worker**: Workers no longer have the logic to scan the media directory.

### Dependencies
- Added `plexapi` to `dashboard/requirements.txt` to support the new Plex integration.