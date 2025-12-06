# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Fixed
- Fixed library type settings not saving when "Sync Between Plex & Jellyfin" is enabled
- Fixed secondary server library list not saving when sync is enabled
- Updated history tab pagination to match job queue pagination style with Previous/Next buttons and smart page window
- Fixed Debug Settings modal not displaying worker_settings data by improving error handling and simplifying the data structure returned by `/api/settings` endpoint

### Changed
- Updated "Sync Between Plex & Jellyfin" tooltip to clarify that it syncs completed transcodes back to both servers
- Modified Jellyfin Configuration Modal footer to ensure all buttons stay on one line with flexbox

### Added
- Added symbolic link detection during media scanning
- Symbolic links are now added to the queue with "awaiting_approval" status and require manual trigger
- Added warning in job queue for symbolic link files explaining that transcoding will increase file size
- Symbolic links show a warning icon and message in the job queue
- Added DEVMODE environment variable for development mode features
- Added Debug Settings button in Options tab (visible only when DEVMODE=true) that displays all database settings in a modal
- Added Christmas theme to theme dropdown with festive red, green, and gold color palette
- Added subtle JavaScript snow animation that activates automatically when Christmas theme is selected
  - Snowflakes fall from top to bottom with natural variation in size, speed, and drift
  - Snow effect automatically starts/stops when switching themes
  - No impact on performance or UI interaction
