# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Stray File Finder**: New tool in the Tools tab to scan media directories for files that don't match expected media or metadata patterns. This helps identify unwanted or leftover files in your media library.

### Changed
- **Passkey Login**: The "Login with Passkey" button is now hidden on the login page if the feature is enabled but no passkeys have been registered in the database yet. This prevents user confusion on a fresh installation.
- **Progress Time Display**: Elapsed time displays on long-running scans now show hours, minutes, and seconds (e.g., "1h 15m 30s") instead of just minutes and seconds (e.g., "75m 30s") when the duration exceeds one hour.

### Fixed