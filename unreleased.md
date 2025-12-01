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
- **Database**: Fixed a bug where database migrations would run on every startup for fresh installations. The initial database setup now correctly sets the schema version, preventing unnecessary migration attempts.
- **UI**: Fixed the "Failed Files Log" modal which was not displaying any failed files due to a column name mismatch in the database query.
- **Security**: Fixed unreachable return statement in authentication middleware that could have been confusing during code reviews.
- **Worker**: Fixed path validation blocking legitimate files when media is mounted at non-standard locations (e.g., `/nfs/media/` instead of `/media/`). The allowed base directories are now configurable via the `MEDIA_PATHS` environment variable.

### Security
- **SSL/TLS Verification**: Added configurable SSL certificate verification for *arr API integrations. A new environment variable `ARR_SSL_VERIFY` (default: `true`) now controls certificate validation. This should only be disabled in development with self-signed certificates. Previously, all *arr API calls had certificate verification disabled.
- **Path Traversal Protection**: Added comprehensive file path validation to prevent path traversal attacks. The worker now validates all file paths before processing to prevent access to system files.
- **SQL Injection Prevention**: Added validation for database user names used in dynamic SQL statements to prevent potential SQL injection if environment variables are compromised.
- **Security Headers**: Added HTTP security headers to all responses including X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, and Permissions-Policy to protect against common web vulnerabilities.
- **Configuration Security**: Updated `.env.example` to remove example credentials and emphasize the need for secure random values. Added new `ARR_SSL_VERIFY` configuration option.
- **Security Documentation**: Added comprehensive `SECURITY.md` file documenting security best practices, known limitations, and vulnerability reporting procedures.
