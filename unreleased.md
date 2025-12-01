# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

### Fixed
- Fixed filepath validation incorrectly blocking all media files due to overly broad sensitive directory check. The validation now correctly allows files under configured MEDIA_PATHS while still blocking access to system directories like /etc, /root, /sys, etc.
