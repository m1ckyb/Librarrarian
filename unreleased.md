# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Jellyfin Library Scanning Support**: Added `run_jellyfin_scan()` function that scans Jellyfin libraries for files needing transcoding, following the same pattern as Plex scanning
- **Post-Transcode Jellyfin Library Updates**: Jellyfin libraries are now automatically refreshed after transcode completion, with proper error handling and respecting the `hide_jellyfin_updates` setting
- **Primary Server Awareness in Scan Button**: Manual and automatic scans now route to the correct media server (Plex, Jellyfin, or Internal) based on the `primary_media_server` setting
- **Jellyfin Support**: Added comprehensive support for Jellyfin media server as an alternative or complement to Plex
  - Jellyfin authentication via API key
  - Jellyfin library discovery and management
  - New Jellyfin login modal with host URL and API key inputs
  - Support for primary media server selection (Plex OR Jellyfin)
  - Toggle to enable multiple media servers for syncing file information to both Plex and Jellyfin
- **Enhanced Logging Controls**: Replaced single "Suppress Verbose Logs" toggle with granular logging controls
  - `hide_job_requests` - Hide worker job request messages from logs
  - `hide_plex_updates` - Hide Plex library update notifications from logs (enabled only if Plex is linked)
  - `hide_jellyfin_updates` - Hide Jellyfin library update notifications from logs (enabled only if Jellyfin is linked)
- **API Endpoints**:
  - `/api/jellyfin/login` - Authenticate and link Jellyfin server
  - `/api/jellyfin/logout` - Unlink Jellyfin server
  - `/api/jellyfin/libraries` - Fetch and manage Jellyfin libraries

### Changed
- **Options Tab**: Renamed "Integrations" section to "Media Servers" to better reflect its purpose
- **Plex Configuration**: Moved Plex server URL from main Options page to Plex login modal for consistency
- **Media Server Selection**: Replaced single media scanner radio buttons with a primary media server dropdown (Plex or Jellyfin)
- **Database Schema**: Updated to version 14 with Jellyfin-related settings and `server_type` column in media_source_types table
- **UI Layout**: Reorganized Media Servers tab to show Plex, Jellyfin, Internal, Sonarr, Radarr, and Lidarr in a cleaner tab structure
- **Logging Configuration**: Replaced "Suppress Verbose Logs" with a dedicated "Logging Options" section containing separate toggles for different log types
- **Database Migration**: Existing `suppress_verbose_logs` setting is automatically migrated to `hide_job_requests` and `hide_plex_updates` in migration #14

### Fixed
- Fixed migration SQL redundancy where default values were being inserted after conditional migration
- Removed deprecated `media_scanner_type` setting from options form processing