# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Fixed
- Fixed snowflake colors not updating when switching between Winter Christmas and Summer Christmas themes - snowflakes now immediately change to the correct colors (white for Winter, festive colors for Summer) when switching themes
- Fixed dashboard crash on root URL (`/`) due to incorrect settings dictionary structure in `get_worker_settings()` function
- Fixed library type settings not saving when "Sync Between Plex & Jellyfin" is enabled
- Fixed secondary server library list not saving when sync is enabled
- Fixed monitored libraries display in sync mode - now correctly shows ONLY primary server's libraries with optional linking dropdown to secondary server, instead of showing both servers' libraries as separate lists
- Updated history tab pagination to match job queue pagination style with Previous/Next buttons and smart page window
- Fixed Debug Settings modal not displaying worker_settings data by flattening the nested dictionary structure in the `/api/settings` endpoint
- Enhanced Debug Settings modal with comprehensive error handling, console logging, and reload functionality for better diagnostics
- Fixed Debug Settings modal showing "Waiting for modal to open..." forever by changing initial message to "Loading settings..." and ensuring Bootstrap modal event handler is properly registered
- Fixed JavaScript console error "Uncaught ReferenceError: $ is not defined" by removing orphaned jQuery code that referenced non-existent DOM elements
- Fixed JavaScript console error "TypeError: response.text().trim is not a function" in update checker by correcting async/await syntax to `(await response.text()).trim()`
- Fixed Debug Settings modal not loading due to app.js being loaded with `defer` attribute causing DOMContentLoaded event to fire before event listeners were registered - now uses conditional initialization based on `document.readyState`
- Fixed critical JavaScript syntax error where main DOMContentLoaded block was missing closing `});` which prevented entire app.js from executing properly
- Fixed library type dropdowns not showing correct selection for Plex music and photo libraries by adding type mapping ('artist' -> 'music', 'photo' -> 'other')
- Fixed monitored libraries badge display in sync mode: Now shows Plex/Jellyfin badges BEFORE library names (matching PR #98 style) instead of "Primary Library" badge after them
- Fixed library linking dropdowns not saving - added database migration v15 to add linked_library column and backend support for link_plex_* and link_jellyfin_* form fields
- Fixed library type and linked library dropdowns not pre-selecting saved values in non-sync mode (when multi-server is disabled)
- Fixed horizontal scrollbar appearing in monitored libraries boxes by adding `overflow-x: hidden` to all library list containers
- Fixed database connection leak in `initialize_database_if_needed()` function - connection now properly closed in finally block
- Improved database migration logic to use TRUNCATE + INSERT pattern instead of UPDATE for schema_version to avoid potential primary key update issues and maintain atomicity
- Added better error handling and logging to migration system with explicit cursor cleanup
- Fixed potential issue where schema_version table could exist but be empty
- Increased combined libraries box max-height from 400px to 500px to prevent secondary library dropdown from being cut off
- Fixed monitored libraries secondary server dropdown being cut off by adjusting column layout: reduced Authentication column from col-md-6 to col-md-4, expanded Monitored Libraries column from col-md-6 to col-md-8
- Fixed form inputs in sync mode being disabled after library lists are populated, preventing settings from being saved when both Plex and Jellyfin are linked
- Made monitored library boxes dynamically sized by removing fixed max-height constraints, allowing them to grow with content

### Changed
- Updated "Sync Between Plex & Jellyfin" tooltip to clarify that it syncs completed transcodes back to both servers
- Modified Jellyfin Configuration Modal footer to ensure all buttons stay on one line with flexbox
- Renamed "Christmas" theme to "Winter Christmas" for clarity
- **Temporarily disabled "Sync Between Plex & Jellyfin" feature** due to persistent issues with settings not being saved correctly (PR #115). The checkbox is now disabled in the UI with a clear "Temporarily Disabled" badge, and database migration v16 ensures the setting is always set to 'false'. This feature will be re-enabled in a future update once the underlying issues are resolved.
- Increased snow animation from 50 to 75 snowflakes for a more festive effect
- Snowflakes now use festive colors (green, red, silver, gold) on Summer Christmas theme instead of white, making them visible on the light background
- Changed Summer Christmas theme background from cream (#fff8dc) to sky blue (#87ceeb) for a more vibrant beach/ocean-like appearance

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
- Added manual Plex token input option to Plex Login Modal
  - Users can now choose between "Login with Credentials" or "Use Existing Token"
  - Added toggle buttons to switch between authentication methods
  - Added text input field for manually entering a Plex authentication token
  - Added helper text explaining where to find the token
  - Implemented backend `/api/plex/save-token` endpoint to validate and save manually provided tokens
  - Modal automatically resets to credentials mode when opened in link mode
- Added comprehensive debugging logs for sync mode form submission troubleshooting
  - Frontend logs show all type and link dropdowns created in combined libraries view
  - Backend logs show all form fields received during settings save
  - Logs help identify if form fields are being created, submitted, and processed correctly
