# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Fixed
- **Database Name Mismatch**: Fixed a critical issue where the `.env` file contained the old database name `transcode_cluster` instead of `librarrarian`, causing the application to fail to connect to the database on fresh deployments.
- **Healthcheck Default User**: Fixed the PostgreSQL healthcheck in `docker-compose.yml` to use the correct default user `transcode` instead of `librarrarian`.
- **Database Initialization Deadlock**: Fixed a critical bug where database tables were not being created on fresh deployments. The `init_db()` function was calling `get_db()` which waits for the `db_ready_event`, but that event was only set after initialization completed, causing a deadlock.
