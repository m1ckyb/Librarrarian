# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Fixed
- **Plex Account Linking**: Improved the Plex account linking process. The Plex Server URL is now saved automatically when linking an account, preventing the URL from being lost on page refresh.

### Added
- **Internal Media Scanner**: Implemented a built-in media scanner as an alternative to Plex. It can scan specified subdirectories within the `/media` volume.
- **Dynamic Folder Selection**: The "Internal Scanner" tab now dynamically lists and allows selection of subdirectories for scanning.

### Changed
- **Redesigned Integrations UI**: The "Plex Integration" section has been refactored into a new "Integrations" section with a tabbed interface (Plex, Internal, Sonarr, Radarr).
- **Conditional UI**: The settings tab and path mapping labels now dynamically update based on the selected media scanner (Plex or Internal), disabling irrelevant options to improve clarity.