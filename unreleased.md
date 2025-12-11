# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Added

### Changed
- **Sonarr Rename Job Optimization**: Renamed episodes are now grouped by series and season before creating jobs. Instead of creating one job per episode file (which could result in hundreds of jobs for a TV series), the system now creates one job per season containing all episodes that need renaming. This significantly reduces the number of jobs in the queue, reduces API calls to Sonarr, and improves processing efficiency. Season-level jobs display the series name, season number, and episode count in the job metadata.

### Fixed
- **Gunicorn Worker Timeout**: Fixed critical issue where the Arr Job Processor thread would cause Gunicorn worker timeouts by using blocking `time.sleep()` calls. Replaced all `time.sleep()` with interruptible `event.wait(timeout)` pattern to prevent the background thread from blocking the Gunicorn worker process during the configurable delay between rename job processing.