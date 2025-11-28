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

### Fixed
- **Plex Path Mapping Logic**: Corrected the logic in the cleanup scanner to ensure path mapping is only performed when the feature is enabled *and* both the "from" and "to" paths are configured.
- **Media Source "Hide" Functionality**: Fixed a critical bug where the "Hide" status for a media source was not saved correctly. This was most noticeable when a Plex library and an Internal folder had the same name, causing the backend to update the wrong record. The form submission process is now unambiguous, ensuring the setting is always applied to the correct source.