# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- Multi-server library linking UI: when "Sync Between Plex & Jellyfin" is enabled, an additional dropdown appears to link libraries between Plex and Jellyfin (Note: backend storage support pending)
- Checkboxes for Jellyfin libraries to match Plex library selection behavior
- "Test Connection" button in Plex login modal to verify server connectivity before authentication
- "Test Connection" button in Jellyfin login modal to verify server connectivity and API key validity
- New API endpoints `/api/plex/test-connection` and `/api/jellyfin/test-connection` for testing server connectivity
- Helper tooltip for "Sync Between Plex & Jellyfin" explaining what the feature does
- "Force" checkbox next to "Clear Queue" button in Job Queue tab - when enabled, will force remove all jobs regardless of status (including encoding jobs)
- "Clear All Errors" button in Failed Files & Stuck Jobs modal footer for easy access to clear all errors from within the modal
- Sortable columns in History & Stats table - click any column header to sort (ID, File, Node, Codec, Size, Reduction, Date)
- Items per page dropdown in History & Stats tab with options: 100, 200, 300, 400, 500 per page, or All

### Changed
- Moved Primary Media Server selection (Plex/Jellyfin/Internal Media Scanner) above Integrations section as a standalone section
- Renamed "Enable Multiple Servers" to "Sync Between Plex & Jellyfin" and moved it to be inline with media server selection
- Renamed "Internal" tab to "Internal Media Scanner" for clarity
- Increased gap between global Start/Stop/Pause buttons from 0px to 4px in Active Nodes tab for improved visual separation (matching individual node buttons)
- Two-column layout for Media Servers tab: authentication controls on left, monitored libraries on right
- Monitored Libraries now shows only the selected server's libraries when sync is disabled, or both when sync is enabled
- Monitored Libraries: Jellyfin library names now display with a purple badge (similar to Plex's orange badge) when "Sync Between Plex & Jellyfin" is enabled
- Options tab: Automatically switches to Internal Media Scanner sub-tab when Internal Media Scanner radio button is selected
- Options tab: Automatically switches to Media Servers sub-tab when Plex or Jellyfin radio button is selected
- Monitored Libraries: When "Sync Between Plex & Jellyfin" is enabled, server badges now appear between the Library Type dropdown and the linking dropdown (Jellyfin badge for Plex libraries, Plex badge for Jellyfin libraries)
- Job Queue: "Force" checkbox for "Clear Queue" button now uses the same attached styling as the "Scan Media" Force checkbox for better visual consistency
- Monitored Libraries: Removed scrollbars from individual Plex and Jellyfin library containers when sync mode is disabled to match the combined list behavior
- History & Stats: Default items per page changed from 15 to 100 for better data visibility
- History & Stats: Default sort order changed to descending by ID (newest first)

### Changed
- Changed "Unlink Plex" button to "Modify Configuration" button when Plex is authenticated
- Changed "Unlink Jellyfin" button to "Modify Configuration" button when Jellyfin is authenticated
- Plex and Jellyfin modals now support both "link" and "modify" modes
- "Unlink" button moved to modal footer for both Plex and Jellyfin
- In modify mode, Plex modal only allows URL changes (credentials fields hidden)
- In modify mode, Jellyfin modal allows both URL and API key changes

### Fixed
- **Critical:** Fixed form save button erasing Plex server URL when saving other settings (Plex URL is now managed exclusively via modal/API)
- **Critical:** Fixed missing Jellyfin path mapping fields in the settings form causing them to be cleared on save
- Fixed "Plex is not configured or authenticated" message appearing when Internal Media Scanner is selected
- Fixed inability to modify Plex server URL after initial linking without unlinking entire account
- Fixed inability to modify Jellyfin server configuration after initial linking without unlinking
- Media Servers tab is now disabled when Internal Media Scanner is selected
- Internal Media Scanner tab is now disabled when Plex or Jellyfin is selected  
- "Sync Between Plex & Jellyfin" checkbox is now disabled and unchecked when Internal Media Scanner is selected
- Library containers now properly show/hide based on primary server selection and sync mode
- Fixed multi-server sync mode to show a single unified "Monitored Libraries" box instead of two separate boxes
- Changed library linking dropdown default option from "-- None --" to "-- Ignore --" for clarity
- Library linking dropdowns now show "not linked" message when secondary server is not authenticated instead of showing "None"
- Improved error messages for Plex/Jellyfin authentication to distinguish between "not configured" and "connection failed" states
- Plex and Jellyfin login now test server connectivity before authentication to provide better error feedback
- Fixed misleading "Plex is not configured or authenticated" error when Plex is linked but server is unreachable
- Fixed Plex test connection and login failing with "Server responded but doesn't appear to be a Plex server" error by properly parsing XML responses from Plex `/identity` endpoint instead of expecting JSON
- Added validation to verify Plex responses have the correct root element (`MediaContainer`) and required attributes
- Added URL validation for Plex server URLs to ensure proper format (http/https scheme and hostname)
- Added content length check (1MB limit) using Content-Length header to prevent memory exhaustion from maliciously large responses
- Extracted duplicate XML parsing logic into reusable helper function for better maintainability
- Fixed Plex server URL not being persisted after initial account linking - page now reloads after successful authentication to ensure settings are properly loaded
- Fixed Jellyfin "Test Connection" button in modify mode showing "Please enter an API key first" error even when API key is saved
- Fixed "Sync Between Plex & Jellyfin" being enabled when only one server is linked (now requires both Plex and Jellyfin to be linked)
- "Sync Between Plex & Jellyfin" is now automatically disabled when either Plex or Jellyfin is unlinked
- Fixed Jellyfin server linking not auto-refreshing the page after successful connection - now matches Plex behavior by reloading the page
- Fixed server badges not displaying in combined libraries view when "Sync Between Plex & Jellyfin" is enabled - badges now correctly appear between Library Type dropdown and linking dropdown

### Notes
- **Plex `--scan` Deprecation Warning**: If you see deprecation warnings about the `--scan` operation in your Plex logs, these are NOT generated by Librarrarian. Librarrarian uses the Plex API (plexapi library) to scan libraries, which is the modern, supported method. These warnings are likely from external automation tools (Sonarr, Radarr, Lidarr, or custom scripts) that directly invoke the Plex Media Scanner executable with the deprecated `--scan` flag. Check your Arr applications' settings and any custom post-processing scripts.
