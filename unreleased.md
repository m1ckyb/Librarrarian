# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Arr Integration Setup**: Added UI in the "Options" tab to configure connection settings (Host and API Key) for Sonarr, Radarr, and Lidarr.
- **Arr Connection Testing**: Implemented a "Test Connection" button for each Arr service that validates the provided credentials and provides immediate feedback.


### Bugs / Buggy Features
- **Media Source Management**: Added advanced controls for media sources in the Integrations tab.
  - **Ignore Option**: A "None" option was added to the media type dropdown, which causes the scanner to ignore that library or folder.
  - **Hide Option**: A "Hide" checkbox was added to each media source, allowing users to hide it from the list.
  - **Show Hidden Toggle**: A "Show Hidden" toggle was added to reveal and edit hidden media sources.