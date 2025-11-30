# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Changed
- **UI Text Clarity**: Renamed the "Scan for Quality" button to "Scan for Quality Mismatches" for better clarity.

### Changed
- **Arr Integration UI**: Added a dismiss button to the "Test Connection" feedback messages for Sonarr, Radarr, and Lidarr, improving user experience by allowing messages to be easily closed.

### Fixed
- **Arr Connection Testing**: Fixed a critical bug where the "Test Connection" button for Sonarr, Radarr, and Lidarr would fail unless the settings were saved first. The test now correctly uses the values from the input fields without requiring a save.
- **Sonarr Settings**: Corrected a bug where the `sonarr_send_to_queue` setting was not being properly handled by the backend.

### Bugs / To Be Fixed
- **Sonarr Scan UI**: There is a persistent race condition where cancelling a Sonarr scan can leave the scan buttons permanently disabled until a page refresh. The UI state management needs to be refactored to ensure it correctly and reliably resets after cancellation.