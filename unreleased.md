# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Fixed
- **Worker Container Crash**: Added a `CMD` instruction to the `worker/Dockerfile` to ensure the `transcode.py` script runs automatically on container start, preventing an immediate exit and restart loop.
- **Worker Dependencies**: Created a `worker/requirements.txt` file and added the `requests` and `psycopg2-binary` dependencies to resolve `ModuleNotFoundError` on startup.
- **Tools UI Overhaul**: Reworked the Sonarr Tools UI to provide immediate, styled feedback for scan progress in a dedicated box. The "Scan" and "Cancel" buttons are now fully functional, using JavaScript to poll for status updates and manage the UI state correctly.
- **Service Startup Order**: Added a healthcheck to the `dashboard` service and updated the `worker` service to depend on the dashboard being healthy. This ensures a stable startup sequence and prevents the worker from starting before the dashboard is ready.

### Changed
- **Worker Hostname**: Set a static hostname (`worker-1`) for the worker container in `docker-compose-dev.yml` to provide a human-readable name in logs and the dashboard UI.