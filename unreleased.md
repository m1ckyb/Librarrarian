# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Media Source Management**: Added advanced controls for media sources in the Integrations tab.
  - **Ignore Option**: A "None" option was added to the media type dropdown, which causes the scanner to ignore that library or folder.
  - **Hide Option**: Items with type set to "None (Hide)" are now hidden from the list by default.
  - **Show Hidden Toggle**: A "Show Hidden" toggle was added to reveal and edit hidden media sources.

### Fixed
- **Media Source Visibility**: Fixed the "Show Hidden" toggle not properly revealing items with type set to "None (Hide)". Previously, these items were always hidden regardless of the toggle state.