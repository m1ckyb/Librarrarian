# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

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
