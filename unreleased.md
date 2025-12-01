# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Fixed
- Fixed filepath validation incorrectly blocking all media files due to overly broad sensitive directory check. The validation now correctly allows files under configured MEDIA_PATHS while still blocking access to system directories like /etc, /root, /sys, etc.
- Fixed VAAPI hardware acceleration initialization failure (FFmpeg exit code 251) by:
  - Adding required VAAPI libraries to worker container (libva, libva-intel-driver, intel-media-driver, mesa-va-gallium)
  - Simplifying VAAPI initialization command from `-init_hw_device vaapi=va:/dev/dri/renderD128 -hwaccel_device va` to `-vaapi_device /dev/dri/renderD128` for more reliable hardware detection
