# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- Primary Media Server selection with radio buttons (Plex/Jellyfin/Internal Media Scanner) in Media Servers tab
- Multi-server library linking: when "Enable Multiple Servers" is enabled, an additional dropdown appears to link libraries between Plex and Jellyfin
- Two-column layout for Media Servers tab: authentication controls on left, monitored libraries on right

### Changed
- Restructured Media Servers tab with side-by-side Plex and Jellyfin authentication sections instead of vertically separated
- Increased gap between Start/Stop/Pause buttons from 2px to 4px in Active Nodes tab for improved visual separation
- Removed horizontal rule separators between Plex and Jellyfin sections in Media Servers tab
- Library containers now always visible, showing appropriate message when not authenticated

### Fixed
- Fixed "Monitored Libraries" incorrectly showing "not configured" message when Plex/Jellyfin was authenticated
- Library lists now load immediately when authenticated instead of requiring display check
