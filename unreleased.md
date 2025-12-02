# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Changed
- **Active Nodes Footer Layout**: Moved the ETA badge from the left side (next to Uptime) to the right side (next to Codec) for better visual grouping of transcoding metrics. The ETA now always displays when a node is actively transcoding, showing "N/A" or "Calculating..." when the estimate is not yet available.

### Fixed
- **ETA Calculation Error**: Fixed "can't subtract offset-naive and offset-aware datetimes" error that occurred when calculating ETA for active transcoding jobs. Both the worker and dashboard now use timezone-aware datetime objects (UTC) for consistent time calculations.
- **Plex Update Log Message**: Clarified log message for post-transcode Plex library updates to distinguish them from automatic scheduled scans. The message now clearly indicates "Post-transcode: Triggering Plex library update to recognize newly encoded file."
