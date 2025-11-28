# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Media Source Management**: Added advanced controls for media sources in the Integrations tab.
  - **Ignore Option**: A "None" option was added to the media type dropdown, which causes the scanner to ignore that library or folder.
  - **Hide Option**: A "Hide" checkbox was added to each media source, allowing users to hide it from the list.
  - **Show Hidden Toggle**: A "Show Hidden" toggle was added to reveal and edit hidden media sources.
- **Node Uptime**: Added an uptime indicator to each worker node card, showing how long the node has been connected to the cluster.
- **Automatic Database Migrations**: Implemented a system to automatically update the database schema on startup, eliminating the need for manual changes or database resets.
- **Plex Path Mapping Toggle**: Added a toggle to enable or disable Plex path mappings. When disabled, the system uses file paths directly from the Plex API, simplifying setup for users whose container paths match their Plex paths.

### Changed
- **CI/CD Migration**: Migrated the CI/CD pipeline from GitHub Actions to Forgejo Actions.
- **Integrations UI**: Replaced static type badges with dropdown menus, allowing users to assign a media type (Movie, TV Show, Music, etc.) to each Plex library and Internal folder. This lays the groundwork for Sonarr/Radarr/Lidarr integration.
- **Path Mapping UI**: The Path Mapping toggle is now correctly shown for the Plex scanner and hidden for the Internal scanner (where it is always active).
- **Path Mapping UI**: Added a tooltip to the Plex Path Mapping toggle to clarify its function.
- **Simplified "Hide" Functionality**: Reworked the "Hide" functionality for media sources to be more intuitive and robust. The separate "Hide" checkbox has been removed. A source is now hidden by selecting the "None (Hide)" option from its media type dropdown. This simplifies the UI and fixes the underlying bug where the hidden state was not being saved correctly.

### Fixed
- **Plex Path Mapping Logic**: Corrected the logic in the cleanup scanner to ensure path mapping is only performed when the feature is enabled *and* both the "from" and "to" paths are configured.
- **Internal Scanner UI**: Fixed a SQL error (`COALESCE types cannot be matched`) that prevented the list of internal media folders from loading in the Options tab. This also indirectly prevented the "Hide" status for internal folders from being saved.