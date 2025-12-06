# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Fixed
- Fixed dashboard crash on root URL (`/`) due to incorrect settings dictionary structure in `get_worker_settings()` function
- Fixed library type settings not saving when "Sync Between Plex & Jellyfin" is enabled
- Fixed secondary server library list not saving when sync is enabled
- **REVERTED PR #106 CHANGES**: Fixed monitored libraries display in sync mode - now correctly shows ONLY primary server's libraries with optional linking dropdown to secondary server, instead of showing both servers' libraries as separate lists (which was ugly and unprofessional)
- Updated history tab pagination to match job queue pagination style with Previous/Next buttons and smart page window
- Fixed Debug Settings modal not displaying worker_settings data by flattening the nested dictionary structure in the `/api/settings` endpoint
- Enhanced Debug Settings modal with comprehensive error handling, console logging, and reload functionality for better diagnostics
- Fixed Debug Settings modal showing "Waiting for modal to open..." forever by changing initial message to "Loading settings..." and ensuring Bootstrap modal event handler is properly registered
- Fixed JavaScript console error "Uncaught ReferenceError: $ is not defined" by removing orphaned jQuery code that referenced non-existent DOM elements
- Fixed JavaScript console error "TypeError: response.text().trim is not a function" in update checker by correcting async/await syntax to `(await response.text()).trim()`
- Fixed Debug Settings modal not loading due to app.js being loaded with `defer` attribute causing DOMContentLoaded event to fire before event listeners were registered - now uses conditional initialization based on `document.readyState`
- Fixed critical JavaScript syntax error where main DOMContentLoaded block was missing closing `});` which prevented entire app.js from executing properly
- Fixed library type dropdowns not showing correct selection for Plex music and photo libraries by adding type mapping ('artist' -> 'music', 'photo' -> 'other')
- Improved library sync display badges: primary libraries now show "Primary Library" badge instead of confusing "Link to Jellyfin/Plex" text, and link dropdowns now have clearer "Link to [Server]:" labels

### Changed
- Updated "Sync Between Plex & Jellyfin" tooltip to clarify that it syncs completed transcodes back to both servers
- Modified Jellyfin Configuration Modal footer to ensure all buttons stay on one line with flexbox
- Renamed "Christmas" theme to "Winter Christmas" for clarity
- Increased snow animation from 50 to 75 snowflakes for a more festive effect

### Added
- Added symbolic link detection during media scanning
- Symbolic links are now added to the queue with "awaiting_approval" status and require manual trigger
- Added warning in job queue for symbolic link files explaining that transcoding will increase file size
- Symbolic links show a warning icon and message in the job queue
- Added DEVMODE environment variable for development mode features
- Added Debug Settings button in Options tab (visible only when DEVMODE=true) that displays all database settings in a modal
  - Added Reload button to manually refresh settings data
  - Added timestamp showing when data was last loaded
  - Added comprehensive console logging for debugging issues
  - Added better error messages with raw API response display when data structure is unexpected
- Added Winter Christmas theme (formerly "Christmas") to theme dropdown with festive red, green, and gold color palette
- Added Summer Christmas theme with bright, beachy colors (sky blue, tropical green, sunshine orange, coral)
- Added subtle JavaScript snow animation that activates automatically when either Christmas theme is selected
  - Snowflakes fall from top to bottom with natural variation in size, speed, and drift
  - Snow effect automatically starts/stops when switching themes
  - Snow effect works with both Winter Christmas and Summer Christmas themes
  - No impact on performance or UI interaction
