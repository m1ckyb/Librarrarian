# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Sonarr Quality Mismatch Scanner**: Added a new scanner and "quality_mismatch" job type. This scan compares a series' quality profile in Sonarr with the quality of its actual episode files. If an episode's quality is below the profile's cutoff, a job is created for the user to investigate a potential upgrade.
- **Arr Integration Setup**: Added UI in the "Options" tab to configure connection settings (Host and API Key) for Sonarr, Radarr, and Lidarr.
- **Arr Connection Testing**: Implemented a "Test Connection" button for each Arr service that validates the provided credentials and provides immediate feedback.
- **Sonarr Rename Jobs**: Added a new "rename" job type. A "Scan Sonarr" button on the Job Queue page will find completed downloads from the Sonarr API and add them to the queue to be renamed.

### Changed
- **Sonarr Rename Strategy**: The rename scanner has been refactored to perform a deep analysis of the entire library by default. This correctly finds older, non-conformant files for renaming, which is the primary goal of this feature. The inefficient "fast scan" has been removed.
- **Database Initialization**: The database schema is now created and configured by the dashboard application on its first startup. This removes the dependency on the `init.sql` file and makes the initial setup more user-friendly, as users no longer need the file present when running `docker-compose up`.

### Fixed
- **Database Name Consistency**: Resolved a technical debt where the worker and dashboard services used different environment variables and default names for the database. Both services now consistently use `DB_NAME` (defaulting to `codecshift`), `DB_USER`, and `DB_PASSWORD`, simplifying configuration.
- **Sonarr Rename Scanner**: Fixed a bug where the rename scanner would not find any files because it was only looking at the last 10 history items. It now correctly scans a larger history, reliably finding all recently imported files.
- **Application Startup**: Fixed a critical bug that caused the application to re-initialize the database on every startup, leading to long boot times. The initialization now correctly runs only once on a fresh database.

### Removed
- The `init.sql` file has been removed from the project root as it is no longer needed.


### Bugs / Buggy Features
- **Media Source Management**: Added advanced controls for media sources in the Integrations tab.
  - **Ignore Option**: A "None" option was added to the media type dropdown, which causes the scanner to ignore that library or folder.
  - **Hide Option**: A "Hide" checkbox was added to each media source, allowing users to hide it from the list.
  - **Show Hidden Toggle**: A "Show Hidden" toggle was added to reveal and edit hidden media sources.