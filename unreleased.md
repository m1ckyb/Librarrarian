# Unreleased Changes

All upcoming features and bug fixes will be documented here until they are part of an official release.

## Added
- **Cleanup Scan Progress Bar**: Cleanup scans now display a real-time progress bar showing the current path being scanned and the percentage complete, replacing the static "Check logs for progress" message.
- **Passkey/WebAuthn Authentication Support**: Added support for passwordless authentication using passkeys (FIDO2/WebAuthn). Users can register and manage multiple passkeys through a new management UI accessible from the navbar. Passkeys work with biometric authentication, security keys, and platform authenticators.
- **User Settings Modal**: Added a new user settings modal accessible via a settings icon in the navbar, providing a centralized location for managing user preferences including passkeys and password changes.
- **Passkey Environment Variables**: Added `PASSKEY_ENABLED`, `WEBAUTHN_RP_ID`, `WEBAUTHN_RP_NAME`, and `WEBAUTHN_ORIGIN` environment variables to docker-compose files for proper passkey configuration.

## Changed
- Cleanup scan progress is now tracked using the existing `scan_progress_state` mechanism for consistency with other scan operations.
- Login page now displays a "Login with Passkey" option when passkey authentication is enabled.
- **Passkey Management UI Relocated**: Moved "Manage Passkeys" button from the Options tab to a new user settings modal in the navbar for better accessibility and organization.

## Fixed
- **Database Initialization**: Fixed missing `passkey_credentials` table error on fresh installations. The table is now properly created during initial database setup instead of only being defined in a migration that would never run.
- **Worker Registration**: Fixed incorrect DASHBOARD_URL in docker-compose.yml (was `http://dashboard:5000`, now `http://librarrarian:5000` to match the actual service name). Workers may fail to register if `API_KEY` is not properly set in the `.env` file - ensure it matches between dashboard and worker configurations.
