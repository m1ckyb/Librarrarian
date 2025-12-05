# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Fixed
- Fixed library type settings not saving when "Sync Between Plex & Jellyfin" is enabled
- Fixed secondary server library list not saving when sync is enabled
- Updated history tab pagination to match job queue pagination style with Previous/Next buttons and smart page window

### Changed
- Updated "Sync Between Plex & Jellyfin" tooltip to clarify that it syncs completed transcodes back to both servers

### Added
- Added symbolic link detection during media scanning
- Symbolic links are now added to the queue with "awaiting_approval" status and require manual trigger
- Added warning in job queue for symbolic link files explaining that transcoding will increase file size
- Symbolic links show a warning icon and message in the job queue
