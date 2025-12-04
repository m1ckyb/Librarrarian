# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- Multi-server library linking UI: when "Sync Between Plex & Jellyfin" is enabled, an additional dropdown appears to link libraries between Plex and Jellyfin (Note: backend storage support pending)
- Checkboxes for Jellyfin libraries to match Plex library selection behavior

### Changed
- Moved Primary Media Server selection (Plex/Jellyfin/Internal Media Scanner) above Integrations section as a standalone section
- Renamed "Enable Multiple Servers" to "Sync Between Plex & Jellyfin" and moved it to be inline with media server selection
- Renamed "Internal" tab to "Internal Media Scanner" for clarity
- Increased gap between global Start/Stop/Pause buttons from 0px to 4px in Active Nodes tab for improved visual separation (matching individual node buttons)
- Two-column layout for Media Servers tab: authentication controls on left, monitored libraries on right
- Monitored Libraries now shows only the selected server's libraries when sync is disabled, or both when sync is enabled

### Fixed
- Fixed "Plex is not configured or authenticated" message appearing when Internal Media Scanner is selected
- Media Servers tab is now disabled when Internal Media Scanner is selected
- Internal Media Scanner tab is now disabled when Plex or Jellyfin is selected  
- "Sync Between Plex & Jellyfin" checkbox is now disabled and unchecked when Internal Media Scanner is selected
- Library containers now properly show/hide based on primary server selection and sync mode
- Fixed multi-server sync mode to show a single unified "Monitored Libraries" box instead of two separate boxes
- Changed library linking dropdown default option from "-- None --" to "-- Ignore --" for clarity
- Library linking dropdowns now show "not linked" message when secondary server is not authenticated instead of showing "None"
