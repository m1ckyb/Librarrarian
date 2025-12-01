# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Job Queue**: Added visual progress bar for manual media scans (Plex/Internal). The scan now shows real-time progress with file count, current file being checked, and elapsed time, similar to the *arr scanner progress bars in the Tools tab.
- **Tools Tab**: Added a "Data Export" section that allows exporting all settings, pending jobs, encoding history, and media source configurations to a JSON backup file.

### Changed
- **Docker**: Migrated both dashboard and worker Dockerfiles to use multi-stage builds with `python:3.14-alpine3.21` base image for significantly smaller image sizes. Replaced `apt-get` commands with Alpine's `apk` package manager.
- **Options Tab**: The "Enable *arr Integration" label now dynamically changes to "Disable *arr Integration" when the integration is enabled, and vice versa.
- **Options Tab**: When an *arr integration is disabled, all related options (host, API key, secondary switches like "Create Rename Jobs in Queue" and "Auto-Rename After Transcode", and the Test Connection button) are now also disabled.
- **Tools Tab**: Simplified section headers from "*arr Tools" to just "*arr" (e.g., "Sonarr Tools" → "Sonarr").

### Fixed
- **Backend**: Fixed a bug where failed job entries were being duplicated in the failed_files table.
- **Worker**: Fixed a critical bug where transcode and rename jobs would fail with "No such file or directory" errors. The worker was not translating file paths from the dashboard's container paths to the worker's local paths for these job types, unlike cleanup jobs which worked correctly.
