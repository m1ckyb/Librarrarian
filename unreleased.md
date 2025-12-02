# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Changed
- Standardized all button styles across the application to use outline buttons (`btn-outline-*`) with consistent color coding and Material Design Icons, matching the style introduced in PR #52 for global node controls
- Updated button styling guidelines in project documentation (remember.md, GEMINI.md, and copilot-instructions.md)
- Standardized all badge styles to use outline/border style matching button aesthetic for visual consistency:
  - Updated "Updated:" clock badge to outline style
  - Updated Active Nodes version badge to outline style
  - Updated Active Nodes footer badges (FPS, Speed, Codec, Idle) to outline style
  - Updated Job Queue Type and Status badges to outline style
  - Updated History table Codec and status badges to outline style
- Plex login modal now auto-dismisses 5 seconds after successful login (previously 1.5 seconds redirect only)
- Changelog modal now displays 5 entries per page with pagination controls instead of one long scrollable page

### Fixed
- Fixed timezone support in Alpine Docker images by installing `tzdata` package - times will now correctly display in the configured timezone instead of UTC