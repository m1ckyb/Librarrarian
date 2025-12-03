# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Jellyfin Support**: Added comprehensive support for Jellyfin media server as an alternative or complement to Plex
  - Jellyfin authentication via API key
  - Jellyfin library discovery and management
  - New Jellyfin login modal with host URL and API key inputs
  - Support for primary media server selection (Plex OR Jellyfin)
  - Toggle to enable multiple media servers for syncing file information to both Plex and Jellyfin
- **Enhanced Logging Controls**: Added new logging control settings to database
  - `hide_job_requests` - Hide worker job request messages from logs
  - `hide_plex_updates` - Hide Plex library update notifications from logs
  - `hide_jellyfin_updates` - Hide Jellyfin library update notifications from logs
- **API Endpoints**:
  - `/api/jellyfin/login` - Authenticate and link Jellyfin server
  - `/api/jellyfin/logout` - Unlink Jellyfin server
  - `/api/jellyfin/libraries` - Fetch and manage Jellyfin libraries

### Changed
- **Options Tab**: Renamed "Integrations" section to "Media Servers" to better reflect its purpose
- **Plex Configuration**: Moved Plex server URL from main Options page to Plex login modal for consistency
- **Media Server Selection**: Replaced single media scanner radio buttons with a primary media server dropdown
- **Database Schema**: Updated to version 14 with Jellyfin-related settings and `server_type` column in media_source_types table
- **UI Layout**: Reorganized Media Servers tab to show Plex, Jellyfin, Internal, Sonarr, Radarr, and Lidarr in a cleaner tab structure

### Fixed