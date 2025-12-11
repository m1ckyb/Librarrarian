# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added
- **Arr Rename Rate Limiting**: Added configurable delay between Arr rename operations to prevent API overload and worker timeouts. The new `arr_rename_delay_seconds` setting (default: 60 seconds) controls how long to wait between processing individual rename jobs. This prevents the dashboard from becoming unresponsive when processing large batches of rename jobs.

### Changed
- **Passkey Login**: The "Login with Passkey" button is now hidden on the login page if the feature is enabled but no passkeys have been registered in the database yet. This prevents user confusion on a fresh installation.
- **Arr Job Processing**: Modified the Arr job processor to process only 1 rename job per iteration instead of 10, which helps prevent worker timeout issues when processing large batches.

### Fixed