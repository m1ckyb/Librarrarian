# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Node Uptime**: Added an uptime indicator to each worker node card, showing how long the node has been connected to the cluster.
- **Plex Path Mapping Toggle**: Added a toggle to enable or disable Plex path mappings. When disabled, the system uses file paths directly from the Plex API, simplifying setup for users whose container paths match their Plex paths.

### Changed
- **CI/CD Migration**: Migrated the CI/CD pipeline from GitHub Actions to Forgejo Actions.
- **Path Mapping UI**: The Path Mapping toggle is now correctly shown for the Plex scanner and hidden for the Internal scanner (where it is always active).

### Fixed
- **Plex Path Mapping Logic**: Corrected the logic in the cleanup scanner to ensure path mapping is only performed when the feature is enabled *and* both the "from" and "to" paths are configured.
