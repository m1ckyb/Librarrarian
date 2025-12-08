# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

## Added
- **Cleanup Scan Progress Bar**: Cleanup scans now display a real-time progress bar showing the current path being scanned and the percentage complete, replacing the static "Check logs for progress" message.
- **Passkey/WebAuthn Authentication Support**: Added support for passwordless authentication using passkeys (FIDO2/WebAuthn). Users can register and manage multiple passkeys through a new management UI in the Options tab. Passkeys work with biometric authentication, security keys, and platform authenticators.

## Changed
- Cleanup scan progress is now tracked using the existing `scan_progress_state` mechanism for consistency with other scan operations.
- Login page now displays a "Login with Passkey" option when passkey authentication is enabled.
