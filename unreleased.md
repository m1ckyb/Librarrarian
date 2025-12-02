# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Changed
- Standardized all progress bars across the dashboard to use a bright, energetic teal color (#1EE4A9) for consistent visual appearance

### Fixed
- Fixed database query error "column reference 'status' is ambiguous" by qualifying column references with table names in queries that join the `jobs` and `nodes` tables
- Fixed force remove button logic: Now only shows for encoding jobs when the worker hasn't sent a heartbeat in 10+ minutes (previously showed based on job age, which didn't account for long-running transcodes)
- Fixed Active Nodes buttons: Start button is now properly disabled when worker is already running; fixed button enable/disable logic to check both worker status and command fields
- Implemented Options modal for worker nodes with Quit Worker Process functionality (previously the Options button did nothing)
- Fixed filepath validation incorrectly blocking all media files due to overly broad sensitive directory check. The validation now correctly allows files under configured MEDIA_PATHS while still blocking access to system directories like /etc, /root, /sys, etc.
- Fixed VAAPI hardware acceleration initialization failure (FFmpeg exit code 251) by:
  - Adding required VAAPI libraries to worker container (libva, libva-intel-driver, intel-media-driver, mesa-va-gallium)
  - Simplifying VAAPI initialization command from `-init_hw_device vaapi=va:/dev/dri/renderD128 -hwaccel_device va` to `-vaapi_device /dev/dri/renderD128` for more reliable hardware detection
