## [0.11.1] - 2025-12-01 - Patch Release

### Fixed
- **Database Name Mismatch**: Fixed a critical issue where the `.env` file contained the old database name `transcode_cluster` instead of `librarrarian`, causing the application to fail to connect to the database on fresh deployments.
- **Healthcheck Default User**: Fixed the PostgreSQL healthcheck in `docker-compose.yml` to use the correct default user `transcode` instead of `librarrarian`.
- **Database Initialization Deadlock**: Fixed a critical bug where database tables were not being created on fresh deployments by refactoring the initialization logic to not have a circular dependency on the `db_ready_event`.
- **Database Role Hardcoding**: Fixed a bug where database initialization would fail if a custom `DB_USER` was set, because some `GRANT` statements were hardcoded to the user `transcode`.

## [0.11.0] - 2025-12-01 - The Arr-ganizer

### Added
- **Auto-Rename After Transcode**: New "Auto-Rename After Transcode" toggle for both Sonarr and Radarr. When enabled, after a transcode job completes, the system will automatically trigger a rescan in the respective Arr application to update media info, then rename the file if your naming format includes codec information (e.g., x265). This follows the renamarr pattern: rescan → update media info → rename.
- **Release Rename Jobs**: Added a new "Release All Renames" button in the Job Queue tab to release Sonarr rename jobs that are awaiting approval. Rename jobs can now be selected and released individually or all at once.
- **Radarr Rename Jobs**: Added full Radarr rename scan support mirroring the Sonarr functionality:
  - Added "Create Rename Jobs in Queue" toggle in the Radarr Options tab. If enabled, creates 'Rename Job' entries in the job queue that require approval. If disabled, files are renamed directly via the Radarr API.
  - Added "Radarr Tools" section in the Tools tab with a "Scan for Renames" button.
  - Added API endpoint `/api/scan/radarr_rename` to trigger Radarr rename scans.
  - The job processor now handles both Sonarr and Radarr rename jobs based on the `source` field in job metadata.
- **Lidarr Rename Jobs**: Added full Lidarr rename scan support mirroring the Sonarr and Radarr functionality:
  - Added "Create Rename Jobs in Queue" toggle in the Lidarr Options tab. If enabled, creates 'Rename Job' entries in the job queue that require approval. If disabled, files are renamed directly via the Lidarr API.
  - Added "Lidarr Tools" section in the Tools tab with a "Scan for Renames" button.
  - Added API endpoint `/api/scan/lidarr_rename` to trigger Lidarr rename scans.
  - The job processor now handles Sonarr, Radarr, and Lidarr rename jobs based on the `source` field in job metadata.
- **VP9 Codec Support**: Added VP9 to the list of codecs eligible for re-encoding. When enabled, VP9-encoded files will be added to the transcode queue instead of being skipped.
- **Job Queue Filtering**: Added filter dropdowns to the Job Queue tab allowing users to filter jobs by type (transcode, cleanup, Rename Job, Quality Mismatch) and status (pending, encoding, failed, etc.). Includes a "Clear Filters" button to reset the view.


### Changed
- **UI Text Clarity**: Renamed the "Scan for Quality" button to "Scan for Quality Mismatches" for better clarity.
- **Job Release API**: The `/api/jobs/release` endpoint now supports multiple job types, allowing both cleanup and Rename Job releases from the same endpoint.
- **Job Queue Checkboxes**: Checkboxes in the job queue now appear for both cleanup and Rename Job types when awaiting approval, not just cleanup jobs.
- **Arr Integration UI**: Added a dismiss button to the "Test Connection" feedback messages for Sonarr, Radarr, and Lidarr, improving user experience by allowing messages to be easily closed.
- **Monitored Libraries UI**: Removed "Hide" switches from Plex and Internal Scanner monitored libraries/folders lists. Items are now hidden from the UI when their media type dropdown is set to "None (Ignore)".
- **Show Ignored Toggle**: Renamed "Show Hidden" toggle to "Show Ignored" for both Plex and Internal Scanner sections to better reflect the new behavior.
- **Scan Button Behavior**: Scan buttons for Sonarr, Radarr, and Lidarr now remain visible but become disabled during an active scan, instead of disappearing. This provides clearer feedback that a scan is in progress.
- **Elapsed Time Format**: The scanning info box now displays elapsed time in a human-readable format (e.g., "1m 04s") instead of just seconds (e.g., "64s").
- **Codec Settings Labels**: Changed "Allow HEVC (H.265)" to "HEVC (H.265)" and "Allow AV1" to "AV1" in the codec eligible for re-encoding settings for better clarity.
- **Scan Completion UI**: Removed the separate "Scan finished" alert popup. The progress bar now shows the completion message directly and resets the UI more quickly (2 seconds instead of 5).
- **Sonarr Integration UI**: Removed "Rescan Time" slider and "Enable Automatic Scanning" checkbox from the Sonarr Options tab. Auto-scanning is no longer supported; scans must be triggered manually via the Tools tab.
- **Reduced Log Noise**: Suppressed frequent polling endpoints (`/api/status` and `/api/scan/progress`) from appearing in the dashboard logs to reduce noise.
- **Sonarr Quality Scan Output**: The Sonarr quality mismatch scan now logs a summary by show (e.g., "Show Name: 5 episode(s)") instead of listing every individual file. The final message also includes the number of affected shows.

### Fixed
- **Sonarr Rename Jobs Processing**: Fixed a critical bug where Sonarr rename jobs created with the "Create Rename Jobs in Queue" option would never be processed. Jobs were created with `awaiting_approval` status but the job processor only looked for `pending` status jobs. Now rename jobs can be released to the queue via the UI.
- **Missing stopProgressPolling Function**: Added the missing `stopProgressPolling` JavaScript function that was being called but never defined, which could cause scan UI issues.
- **Arr Connection Testing**: Fixed a critical bug where the "Test Connection" button for Sonarr, Radarr, and Lidarr would fail unless the settings were saved first. The test now correctly uses the values from the input fields without requiring a save.
- **Sonarr Settings**: Corrected a bug where the `sonarr_send_to_queue` setting was not being properly handled by the backend.
- **View Errors Button**: Fixed the "View Errors" button not working due to missing modal HTML content in the failures_modal.html template.
- ***arr Scan UI Race Condition**: Fixed a persistent race condition where cancelling an *arr scan could leave the scan buttons permanently disabled until a page refresh. The UI now properly saves scan context before async operations and always resets the UI state on errors.
- **Scan Page Load Resume**: Fixed an issue where page load would trigger a new API call instead of just resuming the scan UI when a scan was already in progress.
- **Scan Progress Error Detection**: Improved error detection when polling for scan progress to properly distinguish between successful scan completion and scan failures/conflicts.
- **Theme Dropdown System Preference**: Fixed the theme switcher to respond to system preference changes when "System" (auto) mode is selected.
- **Monitored Libraries Hide Logic**: Fixed the backend logic for determining when a library/folder is hidden. The `is_hidden` flag is now correctly set based on whether the media type dropdown is set to 'none' (Ignore).
- **Scan Buttons Flash Issue**: Fixed a race condition in the background thread that caused scan buttons (Sonarr, Radarr, Lidarr) to flash and do nothing. The thread now uses non-blocking event checks instead of sequential waits, allowing all scan events to be processed immediately.
- **Scan Cancel Event Persistence**: Fixed an issue where the scan cancel event would persist between scans. If a previous scan was cancelled, subsequent scans would immediately appear cancelled. The cancel event is now cleared at the start of each scan attempt.
- **Theme Dropdown Not Opening**: Fixed the theme dropdown not dropping down by adding explicit `type="button"` to dropdown menu items and removing duplicate Bootstrap script loading.
- **Stats Cards Loading**: Fixed *arr stats cards not showing data by adding a null check for the tools tab element and loading stats when navigating directly to the Tools tab via URL hash.
- **Scan Progress Box Position on Refresh**: Fixed an issue where the scan progress box would jump to the wrong section when refreshing the page during an active scan. Added `scan_source` and `scan_type` fields to the scan progress API to reliably track which integration is being scanned.
- **Sonarr Episode Count**: Fixed Sonarr stats showing 0 episodes by changing from `episodeFileCount` (downloaded episodes only) to `episodeCount` (total episodes in library).
- **Failed Files Table Colspan**: Fixed the "No failed files found" message not stretching across all 4 columns in the failed files modal.
- **Scan Buttons After Cancel**: Fixed scan buttons not working immediately after cancelling a scan. The backend now skips the 10-second delay when a scan is cancelled, allowing users to start a new scan immediately.
- **Sonarr Quality Mismatch Scanner**: Fixed the Sonarr quality mismatch scanner to properly detect episodes that don't meet the quality profile's cutoff. The scan now correctly uses the `includeEpisodeFile=true` parameter when fetching episode data from the Sonarr API to get proper quality information. Added detailed logging for each mismatch found.
## [0.10.12] - 2025-11-30 - Patch Release
### Changed
- **Options UI Reorganization**: Consolidated and reorganized settings on the Options page into logical groups ("Transcoding & System", "Maintenance", "File Handling") for improved clarity and user experience.
- **Sonarr Rename Job Handling**: Modified the "Create Rename Jobs in Queue" setting behavior. If selected, rename jobs are now added to the queue with 'awaiting_approval' status. If unselected, rename jobs are automatically performed by directly calling Sonarr's API, bypassing the local job queue.
- **Code Structure**: Refactored all inline JavaScript from `index.html` into a dedicated `dashboard/static/js/app.js` file. This improves maintainability, enables browser caching, and follows web development best practices.

### Fixed
- **Sonarr Tools Buttons & UI**: Correctly implemented the "Scan for Renames" and "Scan for Quality" buttons and their associated JavaScript logic directly within `index.html`. The UI now has separate, functional progress bars and feedback areas for each scan type.
- **Startup Race Condition**: Fixed a critical startup error where background threads would attempt to access the database before it was initialized. Implemented a `threading.Event` to ensure all threads wait until database migrations are complete.
- **Jinja2 TemplateNotFound Errors**: Resolved multiple `TemplateNotFound` errors by creating missing modal template files (`failures_modal.html`, `node_options_modal.html`, `plex_login_modal.html`, `changelog_modal.html`) within the `dashboard/templates/modals` directory.
- **Sonarr Scan UI Visibility**: Corrected the display logic for Sonarr rename and quality scan feedback and progress elements. The progress bar and associated messages now correctly appear within their respective styled container boxes due to updated JavaScript and HTML structure.
- **Progress Box Styling**: Updated the CSS for `.progress-box` to have a transparent background and a green outline, matching the page's background.
- **Sonarr Scan Feedback Display**: Modified the JavaScript to clear the "scan started successfully" feedback message once the progress bar is active, as requested by the user.
- **Indentation Error in dashboard_app.py**: Corrected a recurring `IndentationError` in `dashboard/dashboard_app.py` around line 1321, ensuring all affected lines are now correctly indented.

---
## [0.10.11] - 2025-11-30 - Patch Release
### Changed
- **Sonarr Job Status**: Sonarr-generated jobs (Rename, Quality Mismatch) now default to a `pending` status instead of `awaiting_approval` to allow for immediate internal processing by the dashboard.
- **Cleaner Logs**: Suppressed noisy and repetitive log messages from the Docker container, including the per-series scan progress and the frequent `/api/scan/progress` polling messages, making logs easier to read.
- **UI Reorganization**: Renamed the "Cleanup" tab to "Tools" and moved the Sonarr scanning buttons into it, creating a dedicated space for manual actions and improving the overall UI structure.
- **UI Text Clarity**: Corrected several misleading descriptions in the UI, particularly for the Sonarr "Create Rename Jobs" and "Enable Automatic Scanning" options, to more accurately reflect their function.
- **Sonarr Rename Strategy**: The rename scanner has been refactored to perform a deep analysis of the entire library. This correctly finds older, non-conformant files for renaming, which is the primary goal of this feature. The inefficient "fast scan" has been removed.
- **Database Initialization**: The database schema is now created and configured by the dashboard application on its first startup. This removes the dependency on the `init.sql` file and makes the initial setup more user-friendly, as users no longer need the file present when running `docker-compose up`.
- **UI**: The Sonarr Tools section in the 'Tools' tab is now disabled and shows a link to the settings page if the Sonarr integration is not enabled.
- **Deployment**: The `docker-compose.yml` file has been updated to use pre-built images from GHCR for production, while the original file has been renamed to `docker-compose-dev.yml` for local development.
- **Database**: Upgraded the PostgreSQL database image from version 13 to 16.

### Fixed
- **Media Source Hide/Show**: Correctly implemented the "Hide" functionality for media sources. The hide option is now a separate checkbox and works independently from the "None" media type.
- **24-Hour Time Format**: Fixed the "Use 24-Hour Time Format" toggle by adding the toggle switch to the UI and implementing the necessary JavaScript logic.
- **UI Responsiveness and Scan Feedback**: Resolved a series of critical, cascading bugs that caused the entire UI to freeze during background scans. The backend scan logic was moved into non-blocking background threads, and the frontend JavaScript was refactored to separate long-polling tasks (like scan progress) from the main UI update loop. This fixed the "Updated" clock, ensured scan progress bars appear correctly, and made the "Cancel Scan" button responsive.
- **24-Hour Time Format**: Fixed the "Use 24-Hour Time Format" toggle not working correctly in some browsers by properly specifying time component options.
- **UI Freezing During Scans**: Fixed a major bug where the main UI (including the "Updated" clock) would freeze while a Sonarr scan was in progress. All UI elements now update correctly during a scan.
- **UI Scan Feedback**: Fixed a race condition that often prevented the scan progress bar from appearing. The UI now reliably shows scan progress in the correct "Tools" tab.
- **UI Scan Cancellation**: Fixed a bug where clicking the "Cancel Scan" button would incorrectly display a "scan in progress" error. The cancellation feedback message is now also correctly styled and dismissible.
- **Sonarr Scanner Reliability**: Fixed a series of critical bugs in the Sonarr rename scanner that prevented it from finding or creating jobs. This includes correcting the API usage pattern to properly rescan series before checking for renames.
- **Sonarr Scanner Timeout**: Fixed a Gunicorn worker timeout that occurred when running long Sonarr scans by moving the logic to an asynchronous background thread.
- **Database Name Consistency**: Resolved a technical debt where the worker and dashboard services used different environment variables and default names for the database. Both services now consistently use `DB_NAME` (defaulting to `codecshift`), `DB_USER`, and `DB_PASSWORD`, simplifying configuration.
- **Application Startup**: Fixed a critical bug that caused the application to re-initialize the database on every startup, leading to long boot times. The initialization now correctly runs only once on a fresh database.
- **Media Source Hide/Show**: Fixed the "Hide" functionality for media sources. The hide option is now a separate checkbox instead of being tied to the "None" media type option. This allows users to independently set a source to be ignored ("None" type) while still keeping it visible in the list.
- **Sonarr Job Handling**: Corrected the logic for Sonarr-generated jobs. 'Rename' and 'Quality Mismatch' jobs are now correctly handled as internal dashboard tasks and are no longer sent to worker nodes.
  - A new background process has been added to the dashboard to automatically process pending 'Rename' jobs by calling the Sonarr API.
  - 'Quality Mismatch' jobs now correctly remain in the queue as informational items for the user.
  - The "Clear Queue" button has been updated to also clear all Sonarr-related jobs (Rename, Quality Mismatch) to allow for easy cleanup of these internal jobs.

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
- **Development Mode**: Introduced a `DEVMODE` environment variable. When set to `on`, it bypasses all authentication requirements for requests originating from local IP addresses (`127.0.0.1`, `192.168.*`).
- **Dev Mode UI Indicator**: A prominent "DEV MODE" banner is now displayed in the top-left corner of the dashboard when development mode is active, providing a clear visual cue.
- **Advanced Options Selector**: Added a UI dropdown that allows users to select between "Standard," "Advanced," and "All" options, dynamically showing or hiding complex settings to simplify the user interface.

## [0.10.10] - 2025-11-28 - Maintenance Release

This release introduces several key backend improvements and UI refinements to enhance stability and user experience.

### Added
- **Node Uptime**: Added an uptime indicator to each worker node card, showing how long the node has been connected to the cluster.
- **Automatic Database Migrations**: Implemented a system to automatically update the database schema on startup, eliminating the need for manual changes or database resets.
- **Plex Path Mapping Toggle**: Added a toggle to enable or disable Plex path mappings. When disabled, the system uses file paths directly from the Plex API, simplifying setup for users whose container paths match their Plex paths.

### Changed
- **CI/CD Migration**: Migrated the CI/CD pipeline from GitHub Actions to Forgejo Actions.
- **Integrations UI**: Replaced static type badges with dropdown menus, allowing users to assign a media type (Movie, TV Show, Music, etc.) to each Plex library and Internal folder. This lays the groundwork for Sonarr/Radarr/Lidarr integration.
- **Path Mapping UI**: The Path Mapping toggle is now correctly shown for the Plex scanner and hidden for the Internal scanner (where it is always active).
- **Path Mapping UI**: Added a tooltip to the Plex Path Mapping toggle to clarify its function.

### Fixed
- **Plex Path Mapping Logic**: Corrected the logic in the cleanup scanner to ensure path mapping is only performed when the feature is enabled *and* both the "from" and "to" paths are configured.
- **Internal Scanner UI**: Fixed a SQL error (`COALESCE types cannot be matched`) that prevented the list of internal media folders from loading in the Options tab. This also indirectly prevented the "Hide" status for internal folders from being saved.
- **Plex Media Type Persistence**: Fixed a bug where saved media type and hide settings for Plex libraries would not display correctly after reloading the page. The API was returning the data under the wrong field name, causing the UI to fall back to default values and making it appear as though the settings were not being saved.

---

## [0.10.9] - 2025-11-24 - Integrations & Internal Scanner

This release refactors the media source configuration into a new "Integrations" system and introduces a built-in Internal Media Scanner as a powerful alternative to Plex.

### Added
- **Internal Media Scanner**: Implemented a built-in media scanner that can scan specified subdirectories within the `/media` volume, using `ffprobe` to detect codecs.
- **Dynamic Folder Selection**: The "Internal Scanner" tab now dynamically lists and allows selection of subdirectories for scanning.

### Changed
- **Redesigned Integrations UI**: The "Plex Integration" section has been refactored into a new "Integrations" section with a tabbed interface (Plex, Internal, Sonarr, Radarr).
- **Conditional UI**: The settings tab and path mapping labels now dynamically update based on the selected media scanner (Plex or Internal), disabling irrelevant options to improve clarity.
- **Project Memory**: Updated `remember.md` to include instructions for the AI to read all high-level documentation at the start of each new session for better context.

### Fixed
- **Plex Account Linking**: Improved the Plex account linking process. The Plex Server URL is now saved automatically when linking an account, preventing the URL from being lost on page refresh.

## [0.10.8] - 2025-11-24 - Changelog Viewer

This release adds a user-friendly changelog viewer directly into the dashboard.

### Added
- **In-App Changelog Viewer**: A new "Changelog" link in the footer opens a modal that displays the project's changelog, rendered from Markdown.
- **Smart Changelog Default**: The viewer intelligently detects if the running version is newer than the latest stable release and defaults to showing the `develop` branch changelog if so, ensuring users always see the most relevant information.

---
## [0.10.7b] - 2025-11-24 - Final Polish

This is a minor release with small UI and logging improvements.

### Changed
- **UI Polish**: Removed the "CodecShift" text from the main dashboard header, leaving only the logo for a cleaner look.
- **Logging**: The dashboard now prints a startup banner to the logs, clearly identifying its version when the container starts.

---
## [0.10.7] - 2025-11-24 - Cluster Stability & Management

This is a major release focused on improving the stability, manageability, and deployment process of the entire cluster. It introduces critical features for version management, worker automation, and safe file cleanup, while also fixing numerous bugs related to database initialization, permissions, and state management.

### Added
- **Version Mismatch Detection**: The dashboard and workers now compare versions on startup. A prominent warning is displayed in both the worker's log and the dashboard UI if a mismatch is detected, preventing compatibility issues.
- **Worker Autostart**: A new `AUTOSTART=true` environment variable allows workers to begin processing jobs immediately on startup, bypassing the need for manual intervention from the UI.
- **Cleanup Job Approval Workflow**: Stale file cleanup jobs are now created with an `Awaiting Approval` status. An administrator must manually release them from the UI (individually or all at once) before a worker will process them, adding a critical layer of safety.
- **Individual Job Deletion**: Added the ability to delete any `pending`, `failed`, or `awaiting_approval` job directly from the queue UI.
- **Force Remove for Stuck Jobs**: A "Force Remove" button now automatically appears for any job that has been in the "Encoding" state for more than 10 minutes, allowing for manual resolution of stuck workers.
- **Timezone Configuration**: Added a `TZ` environment variable to the `docker-compose.yml` file, allowing all container logs and timestamps to be set to a local timezone.
- **Path Mapping for Cleanup**: The cleanup scanner now uses the path mapping settings from the UI, allowing it to correctly find and queue stale files in complex setups (e.g., non-Docker workers, NAS mounts).

### Changed
- **Database Initialization**: The database is now initialized using a standard `init.sql` script via Docker's entrypoint mechanism. This is more efficient and resolves all race conditions on a fresh deployment.
- **Default Settings**: The `init.sql` script now populates the `worker_settings` table with a full set of default values, ensuring the dashboard starts correctly on a fresh database.
- **CI/CD Pipeline**: The GitHub Actions workflows have been updated to use the correct build context, resolving build failures and ensuring version consistency between local and automated builds.
- **Version Mismatch Logic**: The dashboard is now the source of truth for version mismatch detection. It periodically checks worker versions and updates their status, ensuring mismatches are caught even if the dashboard is updated while workers are running.

### Fixed
- **Critical Startup Race Condition**: Fixed a series of `relation "nodes" does not exist` and `permission denied` errors that occurred when starting the cluster with a fresh database.
- **Worker Authentication**: Fixed a critical bug where workers could not authenticate with the dashboard after the security features were enabled.
- **Worker State Machine**: Resolved several bugs in the worker's main loop that caused `AUTOSTART` workers to incorrectly go idle after their first job check.
- **Job ID Reuse**: The "Clear Queue" function now uses `DELETE` instead of `TRUNCATE`, preventing the reuse of job IDs and ensuring data integrity with the history table.
- **Stale File Detection**: Corrected the logic for detecting stale temporary files, which now correctly looks for files starting with `tmp_`.

---
## [0.10.6] - 2025-11-24 - Stability Fix

This is a minor stability release that fixes a critical bug with the stale file cleanup feature.

### Fixed
- **Stale File Cleanup Timeout**: Fixed a Gunicorn worker timeout that occurred when queuing a stale file cleanup on large media libraries. The cleanup scan is now a non-blocking, asynchronous background task, providing an instant response to the UI.

---
## [0.10.5] - 2025-11-24 - OIDC Authentication & UI Polish

This release takes the experimental authentication features from the previous version and makes them production-ready. It includes a series of critical bug fixes for the OIDC login flow and several UI enhancements for a more polished user experience.

### Added
- **Dynamic Welcome Message**: The dashboard now greets logged-in users with a dynamic message (e.g., "Good morning," "Good afternoon") based on the server's time of day.

### Changed
- **OIDC Production Ready**: The OpenID Connect (OIDC) integration is now stable and considered ready for production use.
- **UI Polish**:
    - The logged-in user's name and welcome message are now displayed prominently in the main dashboard header.
    - The welcome message was moved to appear after the logout button for better visual flow.
    - The dashboard version in the footer is now read dynamically from `VERSION.txt`, ensuring consistency.
    - The "Logout" button's styling now matches other header buttons for a consistent look.
- **Cleaned Footer**: The user's name and login/logout buttons have been removed from the shared footer to avoid redundancy.

### Fixed
- **OIDC Login Flow**: Fixed a series of critical bugs that prevented the OIDC login from working, including `NameError` on startup, redirect loops, incorrect callback URLs behind a reverse proxy (`Redirect URI Error`), invalid token verification (`Invalid key set format`), and unsupported signing algorithms (`UnsupportedAlgorithmError`).
- **Local Login Loop**: Resolved a redirect loop that occurred during local login attempts.

## [0.10.4] - 2025-11-24 - Secure Access

This release introduces a comprehensive and flexible authentication system to secure the dashboard.

### Added
- **Authentication System**: Implemented a master `AUTH_ENABLED` switch to protect the entire dashboard.
- **Local Login**: Added a local username/password login method, configured via environment variables. The password is required to be base64 encoded for improved security.
- **OIDC Integration (Untested)**: Added support for OpenID Connect (OIDC) as a primary authentication method. This feature is new and should be considered experimental.

---

## [0.10.3] - 2025-11-24 - The Polishing Act

This is a significant stability and bug-fix release that addresses numerous issues across the entire stack, from the worker's core logic to the dashboard's UI rendering.

### Fixed
- **Job Distribution**: Fixed a critical bug where the dashboard would incorrectly report the job queue as "paused", preventing workers from receiving jobs.
- **Progress Bar**: Fixed an issue where the progress bar on worker nodes was not displaying or updating during a transcode.
- **UI State & Rendering**:
    - The "Pause Queue" button now correctly updates to "Resume Queue" to reflect the current state.
    - The "Node" and "Codec" columns in the History table now display correct information instead of "undefined".
    - Fixed a bug causing "undefined" to appear on idle node cards.
    - The live FPS and Speed metrics have been re-implemented and are now correctly displayed in the node card footer.
- **Job Queue Sorting**: The job queue is now correctly sorted to always show "Encoding" jobs at the top for better visibility.

## [0.10.2] - 2025-11-24 - Cluster Control

This release focuses on massive stability improvements, extensive bug fixing, and adding critical quality-of-life features for queue and cluster management.

### Added
- **Manual Plex Scan**: A "Manual Scan" button has been added to the Job Queue page, allowing users to trigger a library scan on demand for immediate feedback.
- **Force Rescan**: A "Force" checkbox was added next to the manual scan button. When checked, the scanner will ignore the existing job and history lists, re-queueing any non-HEVC files it finds.
- **Pause/Resume Job Queue**: A "Pause Queue" button has been added to the UI. When paused, the dashboard will stop distributing new jobs to workers, allowing the cluster to gracefully finish its current work.
- **Clear Job Queue**: A "Clear Queue" button was added to instantly and permanently delete all jobs from the pending queue.
- **Configurable Auto-Scan**: A "Rescan Delay" setting has been added to the Options page. This allows users to define how many minutes the system should wait between automatic scans. Setting it to `0` disables automatic scanning entirely.
- **Job Queue Pagination**: Implemented a full, smart pagination system for the Job Queue page. This prevents the UI from locking up when loading thousands of jobs and makes navigation easy.
- **Centralized Settings API**: Added a new `/api/settings` endpoint to the dashboard, allowing workers to fetch their configuration centrally.

### Changed
- **Asynchronous Scanning**: The manual scan process is now fully asynchronous. The API endpoint immediately returns a response to the UI while the actual scan runs in the background, fixing all Gunicorn worker timeout errors.
- **UI Layout**: The Plex settings on the Options page have been reorganized into a cleaner two-column layout.

### Fixed
- **Critical Scanner Bugs**:
    - Resolved a series of `AttributeError` and `TypeError` crashes that prevented the scanner from correctly reading video codec information from the Plex API.
    - The scanner now correctly calls `video.reload()` to fetch full media details, fixing an issue where all codecs were reported as `N/A`.
    - The scanner now correctly iterates through all of a video's "parts", ensuring it finds the correct video stream even in libraries with optimized versions.
    - The library filter was fixed to correctly identify and scan "Music Videos" and "Other Videos" (e.g., YouTube) libraries.
- **Job Queue Failures**:
    - Fixed a bug where the UI would show "Failed to fetch job queue" because the `/api/jobs` endpoint was missing.
    - Fixed a database commit issue where the scanner would identify files but fail to save them to the job queue.
- **Background Thread Stability**: Fixed a `RuntimeError: Working outside of request context` crash that occurred when the automatic scanner tried to access web request data.
- **UI Auto-Refresh Bug**: The Job Queue page no longer reverts to page 1 on auto-refresh and now correctly stays on the user's currently selected page.
- **Job Queue Rendering**: Fixed a UI rendering bug where a "ghost" job from a previous page would sometimes appear at the bottom of the current page.
- **Standalone Worker Execution**: The worker script now defaults to connecting to `localhost`, fixing a DNS error and allowing it to be run outside of Docker for development and testing.
- **Worker Startup Crash**: Fixed an `AttributeError` that caused the worker script to crash immediately on startup due to an incorrect method name.
- **Form Resubmission Error**: Implemented the Post-Redirect-Get (PRG) pattern for the Options page, eliminating the browser warning on page refresh after saving settings.

## [0.10.1] - 2025-11-23 - The Scanner Awakens

This is a stability release that ensures the new Plex integration features from `v0.10.0` run correctly in a production Docker environment.

### Changed
- **Database Initialization**: The database initialization logic is now handled by a dedicated `init_db.py` script. The `docker-compose.yml` file has been updated to run this script before starting the web server, ensuring the database is ready and preventing race conditions.

### Fixed
- **Plex Scanner in Docker**: Corrected a critical bug where the background Plex scanner thread would not start when the application was run with Gunicorn inside a Docker container. The scanner now initializes correctly, allowing for automated job creation in production.

---

## [0.10.0] - 2025-11-23 - User-Friendly Plex Integration

### Added
- **In-App Plex Authentication**: Implemented a secure, PIN-based OAuth flow directly within the dashboard. Users can now link their Plex account by visiting `plex.tv/link` and entering a code, eliminating the need to handle authentication tokens manually.
- **Dynamic Plex Library Selection**: Once authenticated, the "Options" tab now dynamically fetches and displays a list of the user's available Plex libraries, allowing them to be selected for monitoring via checkboxes.
- **Plex Login/Logout**: Added "Link Plex Account" and "Unlink Plex Account" buttons to the UI for managing the authentication state.

### Changed
- **Configuration Storage**: All Plex-related settings (URL, Token, and Monitored Libraries) are now stored securely in the database and managed via the UI, not in environment files.
- **Options UI**: The "Options" tab was redesigned to support the new Plex authentication flow and dynamic library list.

### Removed
- **Plex Environment Variables**: Removed the requirement for `PLEX_URL`, `PLEX_TOKEN`, and `PLEX_LIBRARIES` in the `.env` file, simplifying the initial setup process.

## [0.9.0] - 2025-11-21 - CodecShift Rebrand & Stability

### Added
- **Dashboard Dockerfile**: Created a `Dockerfile` for the dashboard to ensure all static assets (like the new logo) are correctly included in the container image.
- **Node Health Indicator**: Added a colored dot (green/orange/red) next to each worker's hostname to provide an at-a-glance view of its health based on the last heartbeat.
- **Search & Pagination**: Implemented search and pagination for the history table, making it easier to navigate large numbers of encoded files.

### Changed
- **Project Rebrand**: The project has been renamed from "Transcode Cluster" to **"CodecShift"**. All relevant files, Docker image names, and UI text have been updated.
- **Consolidated UI**: Merged the "History" and "Stats" tabs into a single "History & Stats" tab to simplify the interface.
- **UI Polish**:
  - The "View Errors" button is now consistently styled and only turns red when errors are present, otherwise remaining in its default outline style.
  - The footer now has a more pronounced "glass" effect with increased transparency.

### Fixed
- **Worker Stability**: Resolved a series of critical bugs in the worker's main loop that caused it to stop processing, ignore commands, or disappear from the dashboard while idle. The worker is now significantly more robust.
- **Layout & Stability**: Fixed numerous UI bugs, including:
  - A- A floating pagination bar on the history tab.
  - Inconsistent button colors between tabs.
  - JavaScript errors that broke UI components like the node control buttons.
  - A typo in the footer HTML (`/span>`).

## [0.8.6] - 2025-11-20 - History, Stats & Cleanup

### Added
- **Stats Tab**: A new tab was added to the dashboard to display aggregate statistics, including total files encoded, total original vs. new size, and average space reduction.
- **Stale File Cleanup**: A new "Cleanup" tab was added to find and delete stale `.lock` and `.tmp_` files left behind by crashed workers.
- **Advanced History Management**:
  - The History tab now shows "In Progress" for files currently being encoded.
  - Added a "Clear All History" button to truncate the history table.
  - Added the ability to delete individual entries from the history log.
- **Dynamic Tabs**: The "Stats" and "History" tabs now automatically refresh their content every 5 seconds when active.

### Changed
- **Redundant File Removal**: The worker no longer writes to local `encoded.list` files, relying solely on the database for history tracking.
- **History Logging**: The worker now logs a file to the history table with an `encoding` status when it starts a job, and updates it to `completed` upon success.

## [0.8.5] - 2025-11-20 - State Management & UI Stability

### Fixed
- **UI Stability**: Resolved a long-standing bug where the "Start" and "Stop" buttons would flip incorrectly. When "Stop" is pressed during a transcode, the worker now enters an intermediate `finishing` state. This allows the UI to correctly reflect the worker's intent to stop, enabling the "Start" button to cancel the stop request.

### Bugs
- **Quit Command Reliability**: The "Quit" command is not always responsive and can be ignored if a worker is in the middle of a long transcode process.

## [0.8.1] - 2025-11-20 - Granular Control & Advanced Config

### Added
- **Granular Node Control**: Replaced the single toggle button with individual "Start", "Stop", and "Pause"/"Resume" buttons for clearer and more precise control over each worker.
- **Pause/Resume Functionality**: Implemented the ability to pause a transcode in progress and resume it later. The worker sends the appropriate signals (`SIGSTOP`/`SIGCONT`) to the `ffmpeg` process.
- **Advanced Transcoding Configuration**: Exposed core transcoding parameters in the "Options" tab of the UI, allowing for dynamic configuration of:
  - Constant Quality (CQ/CRF) values for each encoder type (NVIDIA, VAAPI, CPU) and resolution (HD/SD).
  - The pixel width threshold that defines a video as "HD".
  - The list of scannable file extensions.
- **Debug Flag**: Re-introduced the `--debug` command-line flag for the worker script. When used, it overrides the database setting and prints the full `ffmpeg` command to the console for easier troubleshooting.

### Changed
- The worker's main loop was refactored to fetch and use the new advanced transcoding settings from the database.

## [0.8.0] - 2025-11-20 - Remote Control & Centralization

### Added
- **Full Remote Control**: Added toggleable "Start" and "Stop" buttons for each node on the dashboard, allowing for complete remote management of the cluster's state.
- **Centralized Configuration**: All worker command-line arguments (e.g., `--allow-hevc`, `--force-nvidia`) are now configurable via the "Options" tab in the dashboard.

### Changed
- **Worker Logic**: Workers now start in an `idle` state and wait for a "Start" command from the dashboard before beginning to process files.
- **Database-Driven Workers**: The worker script (`transcode.py`) has been refactored to fetch all its configuration from the database. It now only requires the media directory as a command-line argument, simplifying deployment.
- **Hardware Detection**: The hardware probing logic was significantly improved to be more reliable, especially for detecting NVIDIA GPUs on systems running Docker or Windows Subsystem for Linux (WSL).

### Fixed
- **Start Command**: Resolved a series of bugs that prevented the "Start" command from working correctly, including database column name mismatches and frontend/backend communication errors.

## [0.7.4] - 2025-11-20 - CSS Loading Fix

### Fixed
- **CSS Loading Order**: Moved the Bootstrap CSS link to the `base.html` template to ensure it loads before custom styles that depend on it. This fixed two resulting bugs:
  - The footer in dark mode now has the correct background color.
  - The badge on the "View Errors" button has the correct text contrast on all button colors.

## [0.7.3] - 2025-11-20 - UI Refinements

### Changed
- **Dashboard UI**: Merged the `/options` page into a new "Options" tab on the main dashboard to consolidate all controls in one place.
- **Dashboard Layout**: Refined the header layout by moving the "View Errors" button inline with the page title and placing the "Updated" clock on its own line for better alignment.

### Fixed
- **UI Visibility**: Improved the text contrast of the badge on the "View Errors" button to ensure it is readable against all background colors (e.g., green or red).
- **Dark Mode Footer**: The footer in dark mode is now darker, providing better visual separation from the page content.

## [0.7.2] - 2025-11-20 - CSS Fixes

### Fixed
- **Dashboard UI**: Fixed several CSS issues to improve the layout and consistency of the dashboard.
  - Moved the "View Errors" button into the footer to prevent it from overlapping with other content.
  - Made the page titles consistent across the dashboard by using `<h1>` tags for all pages.
  - Removed unnecessary `padding-bottom` from the `body` element.

## [0.7.1] - 2025-11-19 - The Non-Interactive Fix

### Changed
- **Worker Self-Update**: The self-update mechanism is now non-interactive to prevent terminal-related bugs within Docker. An `--update` command-line flag was added to enable this, and it is now the default for the Docker Compose service.

### Fixed
- **Update Prompt Bug**: Fixed a bug where the interactive update prompt would not accept input inside a Docker container due to line ending issues (`^M`).

## [0.7.0] - 2025-11-19 - The Boring & Broken Update

### Fixed
- **Worker Rescan Delay**: Corrected a critical bug where the worker would ignore the user-defined rescan delay and default to a 60-second wait. The delay now works as intended.
- **Dashboard Layouts**: Fixed numerous UI layout and rendering bugs across the dashboard.
  - Corrected the active node card display, which was broken due to a copy-paste error.
  - Moved the "Updated" timestamp and theme switcher to the footer to create a consistent header and prevent layout shifting on all pages.
- **Worker Self-Update**: The worker's self-update check now correctly points to the `develop` branch, resolving "404 Not Found" errors.
- **Dashboard Stability**: Added a `secret_key` to the Flask application, resolving crashes related to session management when saving options.
- **Dashboard Robustness**: The options page is now resilient and will no longer crash if the worker has not yet populated the settings in the database.

## [0.6.0] - 2025-11-19 - Command & Control

### Added
- **Worker Options Page**: Created a new `/options` page in the dashboard to allow for dynamic configuration of worker behavior.
- **Database-Driven Settings**: Implemented a new `worker_settings` table in the database to store and persist configuration, with sensible defaults.
- **Configurable Rescan Delay**: Added an option with a slider (0-60 minutes) to set a delay before workers rescan for files after a successful batch.
- **Configurable Folder Exclusion**: Added an option to make workers completely ignore directories named `encoded`.

### Changed
- **Worker Logic**: The worker now fetches the latest settings from the database at the start of every scan cycle and applies them.

## [0.5.0] - 2025-11-19 - Into the Darkness

### Added
- **UI Theme Switcher**: Implemented a full-featured theme switcher in the dashboard with support for Light, Dark, and System-default modes. The user's preference is saved in local storage.

### Changed
- **Footer Layout**: The dashboard footer was redesigned with a split layout, placing the version on the left and the project link on the right.
- **Template Inheritance**: Refactored the dashboard's frontend by creating a `base.html` template to centralize the page structure, theme logic, and footer, simplifying `index.html`.


## [0.4.2] - 2025-11-19

### Changed
- **Worker Versioning**: The worker script will now fall back to a version identifier of `"standalone"` if the `VERSION.txt` file is not found, preventing crashes when run outside of the main project structure.

### Fixed
- **Dashboard UI**: Added padding to the bottom of the dashboard page to prevent the fixed footer from overlapping the "View Errors" button.

## [0.4.1] - 2025-11-19

### Added
- **Centralized Versioning**: Created a single `VERSION.txt` file at the project root to act as the single source of truth for versioning across all components.
- **UI Polish**: The dashboard footer is now fixed to the bottom of the page with a semi-transparent "glassy" effect.
- **Conditional UI**: The "Clear Errors" button on the dashboard is now hidden if there are no errors to clear.


## [0.4.0] - 2025-11-19

### Added
- **FPS Display**: The dashboard now shows the Frames Per Second (FPS) for each active transcoding node.
- **Dynamic Error Button**: The "View Errors" button is now green when there are no errors and red if errors are present.
- **Local Timestamp**: The "Updated" timestamp now reflects the user's local browser time.
- **Application Footer**: Added a footer to the dashboard containing the web UI version and a link to the project's GitHub repository.