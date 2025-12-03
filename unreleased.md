# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Failed Transcode Detection**: The dashboard now detects when a job is stuck in "Encoding" status while the assigned worker is processing higher job IDs. This indicates a failed transcode that wasn't properly reported. Stuck jobs display "Remove" and "Re-add to Queue" buttons in the action column.
- **Re-queue Job API**: Added `/api/jobs/requeue/<job_id>` endpoint to reset a stuck job back to pending status, allowing workers to retry the transcode.
- **Stuck Jobs in Errors Modal**: Stuck jobs are now treated as errors and appear in the "View Errors" modal alongside regular failed files. The "View Errors" button now lights up (turns red) when there are stuck jobs. Each stuck job in the modal displays "Re-add" and "Clear" action buttons for easy management.

### Changed
- **Active Nodes Footer Layout**: Moved the ETA badge from the left side (next to Uptime) to the right side (next to Codec) for better visual grouping of transcoding metrics. The ETA now always displays when a node is actively transcoding, showing "N/A" or "Calculating..." when the estimate is not yet available.
- **Errors Modal Layout**: Updated the errors modal to use an "Actions" column instead of "Log" column, with a wider modal size (modal-xl) to accommodate action buttons. The modal title now reads "Failed Files & Stuck Jobs" to reflect both types of errors.

### Fixed
- **Worker Crash on FFmpeg Unicode Output**: Fixed `UnicodeDecodeError` that caused workers to crash when FFmpeg output contained non-UTF-8 characters (e.g., special progress bar characters). The worker now handles encoding errors gracefully by replacing invalid characters instead of crashing.
- **ETA Calculation Error**: Fixed "can't subtract offset-naive and offset-aware datetimes" error that occurred when calculating ETA for active transcoding jobs. Both the worker and dashboard now use timezone-aware datetime objects (UTC) for consistent time calculations.
- **Plex Update Log Message**: Clarified log message for post-transcode Plex library updates to distinguish them from automatic scheduled scans. The message now clearly indicates "Post-transcode: Triggering Plex library update to recognize newly encoded file."
- **ETA Timezone Display**: Fixed ETA times being displayed in UTC instead of the configured timezone. The dashboard now respects the `TZ` environment variable and displays ETA and last_updated times in the user's configured timezone.
- **Stuck Job Detection**: Jobs that fail silently (worker crashes or loses connection) are now automatically detected when the worker comes back online and processes higher job IDs. The UI provides actions to remove or re-queue these stuck jobs.
- **FileNotFoundError After Transcode**: Fixed `FileNotFoundError` that occurred when the original file was moved or deleted by external processes (Plex, Sonarr, etc.) during transcoding. The worker now captures the original file size before starting the transcode and gracefully handles cases where the original file disappears, completing the job with the transcoded file.
