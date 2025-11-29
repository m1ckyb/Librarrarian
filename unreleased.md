# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Elapsed Time for Scans**: The UI now displays an elapsed time counter next to the progress bar during Sonarr scans.
- **24-Hour Time Format**: Added a UI option in the "Options" tab to display the "Updated" clock in a 24-hour format.
- **Cancellable Scans**: Sonarr scans can now be cancelled via a "Cancel" button that appears in the UI while a scan is in progress.
- **Integration Toggles**: Added master "Enable" toggles for the Sonarr, Radarr, and Lidarr integrations, allowing users to completely disable services that are not in use.
- **Sonarr Quality Mismatch Scanner**: Added a new scanner and "quality_mismatch" job type. This scan compares a series' quality profile in Sonarr with the quality of its actual episode files. If an episode's quality is below the profile's cutoff, a job is created for the user to investigate a potential upgrade.
- **Arr Integration Setup**: Added UI in the "Options" tab to configure connection settings (Host and API Key) for Sonarr, Radarr, and Lidarr.
- **Arr Connection Testing**: Implemented a "Test Connection" button for each Arr service that validates the provided credentials and provides immediate feedback.
- **Sonarr Rename Jobs**: Added a new "rename" job type. A "Scan Sonarr" button on the Job Queue page will find completed downloads from the Sonarr API and add them to the queue to be renamed.
- **Media Source Management**: Added advanced controls for media sources in the Integrations tab.
  - **Ignore Option**: A "None" option was added to the media type dropdown, which causes the scanner to ignore that library or folder.
  - **Hide Option**: A "Hide" checkbox was added to each media source, allowing users to hide it from the list.
  - **Show Hidden Toggle**: A "Show Hidden" toggle was added to reveal and edit hidden media sources.

### Changed
- **Cleaner Logs**: Suppressed noisy and repetitive log messages from the Docker container, including the per-series scan progress and the frequent `/api/scan/progress` polling messages, making logs easier to read.
- **UI Reorganization**: Renamed the "Cleanup" tab to "Tools" and moved the Sonarr scanning buttons into it, creating a dedicated space for manual actions and improving the overall UI structure.
- **UI Text Clarity**: Corrected several misleading descriptions in the UI, particularly for the Sonarr "Create Rename Jobs" and "Enable Automatic Scanning" options, to more accurately reflect their function.
- **Sonarr Rename Strategy**: The rename scanner has been refactored to perform a deep analysis of the entire library. This correctly finds older, non-conformant files for renaming, which is the primary goal of this feature. The inefficient "fast scan" has been removed.
- **Database Initialization**: The database schema is now created and configured by the dashboard application on its first startup. This removes the dependency on the `init.sql` file and makes the initial setup more user-friendly, as users no longer need the file present when running `docker-compose up`.

### Fixed
- **24-Hour Time Format**: Fixed the "Use 24-Hour Time Format" toggle not working correctly in some browsers by properly specifying time component options.
- **UI Freezing During Scans**: Fixed a major bug where the main UI (including the "Updated" clock) would freeze while a Sonarr scan was in progress. All UI elements now update correctly during a scan.
- **UI Scan Feedback**: Fixed a race condition that often prevented the scan progress bar from appearing. The UI now reliably shows scan progress in the correct "Tools" tab.
- **UI Scan Cancellation**: Fixed a bug where clicking the "Cancel Scan" button would incorrectly display a "scan in progress" error. The cancellation feedback message is now also correctly styled and dismissible.
- **Sonarr Scanner Reliability**: Fixed a series of critical bugs in the Sonarr rename scanner that prevented it from finding or creating jobs. This includes correcting the API usage pattern to properly rescan series before checking for renames.
- **Sonarr Scanner Timeout**: Fixed a Gunicorn worker timeout that occurred when running long Sonarr scans by moving the logic to an asynchronous background thread.
- **Database Name Consistency**: Resolved a technical debt where the worker and dashboard services used different environment variables and default names for the database. Both services now consistently use `DB_NAME` (defaulting to `codecshift`), `DB_USER`, and `DB_PASSWORD`, simplifying configuration.
- **Application Startup**: Fixed a critical bug that caused the application to re-initialize the database on every startup, leading to long boot times. The initialization now correctly runs only once on a fresh database.
- **Media Source Hide/Show**: Fixed the "Hide" functionality for media sources. The hide option is now a separate checkbox instead of being tied to the "None" media type option. This allows users to independently set a source to be ignored ("None" type) while still keeping it visible in the list.

### Removed
- The `init.sql` file has been removed from the project root as it is no longer needed.