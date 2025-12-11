# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added

### Changed

### Fixed
- **Gunicorn Worker Timeout**: Fixed critical issue where the Arr Job Processor thread would cause Gunicorn worker timeouts by using blocking `time.sleep()` calls. Replaced all `time.sleep()` with interruptible `event.wait(timeout)` pattern to prevent the background thread from blocking the Gunicorn worker process during the configurable delay between rename job processing.