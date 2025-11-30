# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Fixed
- **UI Sonarr Scan Progress**: Fixed a race condition and display issue where the Sonarr scan progress box was not showing immediately when a scan was initiated from the Tools tab. The UI now provides immediate visual feedback ("Starting scan...") and correctly polls for progress updates.
- **Worker Container Crash**: Added a `CMD` instruction to the `worker/Dockerfile` to ensure the `transcode.py` script runs automatically on container start, preventing an immediate exit and restart loop.