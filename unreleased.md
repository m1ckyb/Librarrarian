# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Estimated Finish Time**: Active nodes now display an estimated finish time (ETA) badge in the footer when transcoding. The ETA is calculated based on current progress and FPS, providing users with an estimate of when the transcode will complete.
- **Database Backup System**: Implemented automated daily database backups to `/data/backup/` directory. Backups are compressed PostgreSQL dumps with timestamps, and the system automatically retains the last 7 backups while removing older ones.
- **Configurable Backup Time**: Added ability to configure the time of day for automatic database backups in the Maintenance section of Options (default: 02:00)
- **Manual Backup**: Added "Run Backup Now" button in the Maintenance section to trigger immediate database backups on demand
- **Backup Management Modal**: Added new "Manage Backups" button in the Maintenance section that opens a modal displaying all backup files with their size and creation date, with options to download or delete individual backups
- **Backup Enable/Disable Toggle**: Added ability to enable or disable automatic database backups in the Maintenance section (enabled by default)
- **Configurable Backup Retention**: Added setting to configure how many backup files to keep (default: 7 days). Older backups are automatically deleted when retention limit is exceeded

### Changed
- **Backup Filename Format**: Changed database backup filename format from `librarrarian_backup_YYYYMMDD_HHMMSS.sql.gz` to `YYYYMMDD.HHMMSS.tar.gz` for better readability and consistency (note: content is still a gzipped SQL dump, but filename uses .tar.gz extension for standardization)
- **Options Page Layout**: Removed horizontal lines between settings in the "Transcoding & System" section for a cleaner, more modern appearance
- **Backup Section Title**: Changed "Database Backup Time" to "Database Backup" in the Maintenance section for better clarity and to accommodate the new enable/disable toggle and retention settings
- **Backup Cleanup Logic**: Updated backup cleanup to respect the configurable retention policy instead of always keeping exactly 7 backups
- **Automatic Rescan Delay**: Changed from minutes to hours for better usability. Setting to 0 still disables automatic scanning. The UI now displays and accepts hours with 0.25-hour increments (15-minute precision)

### Fixed
- **Backup Error Handling**: Improved backup process to properly check both pg_dump and gzip for errors, preventing silent backup corruption. Failed backups now clean up incomplete files automatically.
- **Backup Cleanup Compatibility**: Backup cleanup now handles both old format (`librarrarian_backup_*.sql.gz`) and new format (`*.tar.gz`) files during the transition period
- Standardized all button styles across the application to use outline buttons (`btn-outline-*`) with consistent color coding and Material Design Icons, matching the style introduced in PR #52 for global node controls
- Updated button styling guidelines in project documentation (remember.md, GEMINI.md, and copilot-instructions.md)
- Standardized all badge styles to use outline/border style matching button aesthetic for visual consistency:
  - **Active Nodes Footer**: Changed "Uptime" text to badge style (badge-outline-secondary)
  - Updated "Updated:" clock badge to outline style
  - Updated Active Nodes version badge to outline style
  - Updated Active Nodes footer badges (FPS, Speed, Codec, Idle) to outline style
  - Updated Job Queue Type and Status badges to outline style
  - Updated History table Codec and status badges to outline style
  - **Tools Tab**: Changed Sonarr, Radarr, and Lidarr "Disabled" badges from solid `bg-secondary` to outline style (`badge-outline-secondary`)
  - **History & Stats Tab**: Changed Average Reduction card from solid background color to outline border style with colored text while maintaining performance-based color coding (green/yellow/red)
- Plex login modal now auto-dismisses 5 seconds after successful login (previously 1.5 seconds redirect only)
- Changelog modal now displays 5 entries per page with pagination controls instead of one long scrollable page
- **Docker Compose**: Added `./librarrarian:/data` volume mount to dashboard service for backup storage

### Removed
- **Obsolete Settings**: Removed "Enable Worker Auto-Update", "Clean Failed Jobs on Start", and "Enable Debug Logging" settings from the Maintenance section as they were non-functional and no longer relevant with the Docker-based architecture

### Fixed
- **Logging Suppression**: Added `/api/health` to the list of suppressed endpoints to reduce noisy debug log entries. Both `/api/status` and `/api/health` are now filtered from access logs as they are polled frequently by the UI
- Fixed timezone support in Alpine Docker images by installing `tzdata` package - times will now correctly display in the configured timezone instead of UTC
- **Pagination Z-Index**: Fixed Job Queue and History pagination page numbers showing through the footer by adding `z-index: 1050` to the footer CSS
- **Dashboard Startup Error**: Fixed `NameError: name 'require_login' is not defined` that prevented the dashboard from starting. Removed incorrect `@require_login` decorator from `/api/backup/now` endpoint as all routes are already protected by the `@app.before_request` hook
- **Database Backup Failure**: Fixed database backup failing with "No such file or directory: 'pg_dump'" by adding `postgresql-client` package to dashboard Dockerfile. Also fixed backup process incorrectly reporting "pg_dump returned None" by properly waiting for the pg_dump process to complete before checking its return code
- **Database Backup Thread Error**: Fixed "Working outside of application context" error in `database_backup_thread` by wrapping database operations with Flask's `app.app_context()`, following the same pattern used by other background threads