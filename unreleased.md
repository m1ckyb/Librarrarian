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

### Changed
- **UI Text Clarity**: Renamed the "Scan for Quality" button to "Scan for Quality Mismatches" for better clarity.
- **Job Release API**: The `/api/jobs/release` endpoint now supports multiple job types, allowing both cleanup and Rename Job releases from the same endpoint.
- **Job Queue Checkboxes**: Checkboxes in the job queue now appear for both cleanup and Rename Job types when awaiting approval, not just cleanup jobs.

### Changed
- **Arr Integration UI**: Added a dismiss button to the "Test Connection" feedback messages for Sonarr, Radarr, and Lidarr, improving user experience by allowing messages to be easily closed.

### Fixed
- **Sonarr Rename Jobs Processing**: Fixed a critical bug where Sonarr rename jobs created with the "Create Rename Jobs in Queue" option would never be processed. Jobs were created with `awaiting_approval` status but the job processor only looked for `pending` status jobs. Now rename jobs can be released to the queue via the UI.
- **Missing stopProgressPolling Function**: Added the missing `stopProgressPolling` JavaScript function that was being called but never defined, which could cause scan UI issues.
- **Arr Connection Testing**: Fixed a critical bug where the "Test Connection" button for Sonarr, Radarr, and Lidarr would fail unless the settings were saved first. The test now correctly uses the values from the input fields without requiring a save.
- **Sonarr Settings**: Corrected a bug where the `sonarr_send_to_queue` setting was not being properly handled by the backend.

### Bugs / To Be Fixed
- **Sonarr Scan UI**: There is a persistent race condition where cancelling a Sonarr scan can leave the scan buttons permanently disabled until a page refresh. The UI state management needs to be refactored to ensure it correctly and reliably resets after cancellation.