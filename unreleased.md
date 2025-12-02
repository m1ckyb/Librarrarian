# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Estimated Finish Time**: Active nodes now display an estimated finish time (ETA) badge in the footer when transcoding. The ETA is calculated based on current progress and FPS, providing users with an estimate of when the transcode will complete.
- **Database Backup System**: Implemented automated daily database backups to `/data/backup/` directory. Backups are compressed PostgreSQL dumps with timestamps, and the system automatically retains the last 7 backups while removing older ones.
- **Configurable Backup Time**: Added ability to configure the time of day for automatic database backups in the Maintenance section of Options (default: 02:00)
- **Manual Backup**: Added "Run Backup Now" button in the Maintenance section to trigger immediate database backups on demand

### Changed
- **Backup Filename Format**: Changed database backup filename format from `librarrarian_backup_YYYYMMDD_HHMMSS.sql.gz` to `YYYYMMDD.HHMMSS.tar.gz` for better readability and consistency (note: content is still a gzipped SQL dump, but filename uses .tar.gz extension for standardization)
- **Options Page Layout**: Removed horizontal lines between settings in the "Transcoding & System" section for a cleaner, more modern appearance

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

### Fixed
- Fixed timezone support in Alpine Docker images by installing `tzdata` package - times will now correctly display in the configured timezone instead of UTC
- **Pagination Z-Index**: Fixed Job Queue and History pagination page numbers showing through the footer by adding `z-index: 1050` to the footer CSS
- **Dashboard Startup Error**: Fixed `NameError: name 'require_login' is not defined` that prevented the dashboard from starting. Removed incorrect `@require_login` decorator from `/api/backup/now` endpoint as all routes are already protected by the `@app.before_request` hook
- **Database Backup Failure**: Fixed database backup failing with "No such file or directory: 'pg_dump'" by adding `postgresql-client` package to dashboard Dockerfile. Also fixed backup process incorrectly reporting "pg_dump returned None" by properly waiting for the pg_dump process to complete before checking its return code