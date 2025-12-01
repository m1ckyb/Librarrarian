# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Job Queue**: Added visual progress bar for manual media scans (Plex/Internal). The scan now shows real-time progress with file count, current file being checked, and elapsed time, similar to the *arr scanner progress bars in the Tools tab.
- **Tools Tab**: Added a "Data Export" section that allows exporting all settings, pending jobs, encoding history, and media source configurations to a JSON backup file.

### Changed
- **Options Tab**: The "Enable *arr Integration" label now dynamically changes to "Disable *arr Integration" when the integration is enabled, and vice versa.
- **Options Tab**: When an *arr integration is disabled, all related options (host, API key, secondary switches like "Create Rename Jobs in Queue" and "Auto-Rename After Transcode", and the Test Connection button) are now also disabled.
- **Tools Tab**: Simplified section headers from "*arr Tools" to just "*arr" (e.g., "Sonarr Tools" → "Sonarr").

### Fixed
- **Backend**: Fixed a bug where failed job entries were being duplicated in the failed_files table.
