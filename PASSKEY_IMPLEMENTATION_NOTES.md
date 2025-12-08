# Passkey/WebAuthn Authentication Implementation Notes

This document outlines what would be needed to implement passkey/WebAuthn authentication for Librarrarian.

## Overview

Passkey authentication would provide a passwordless login option using FIDO2/WebAuthn standards. This is a complex security feature that requires careful implementation.

## Requirements

### 1. Prerequisites
- **HTTPS Required**: WebAuthn only works over HTTPS (except localhost for development)
- **Modern Browser**: Users need a browser that supports WebAuthn API
- **Authenticator**: Users need a compatible authenticator (biometric, security key, or platform authenticator)

### 2. Database Schema

Add a new table to store passkey credentials:

```sql
CREATE TABLE passkey_credentials (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,  -- Maps to LOCAL_USER or OIDC user
    credential_id TEXT NOT NULL UNIQUE,  -- Base64-encoded credential ID
    public_key TEXT NOT NULL,  -- Base64-encoded public key
    counter BIGINT NOT NULL DEFAULT 0,  -- Signature counter for replay protection
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP WITH TIME ZONE,
    device_name VARCHAR(255),  -- User-friendly name for the device
    UNIQUE(user_id, credential_id)
);
```

### 3. Backend Implementation

#### Required Python Libraries
```python
# Add to dashboard/requirements.txt
webauthn>=2.0.0  # WebAuthn library for Python
```

#### API Endpoints Needed

1. **Registration Challenge** (`POST /api/auth/passkey/register/challenge`)
   - Generates a challenge for credential creation
   - Returns PublicKeyCredentialCreationOptions

2. **Registration Verification** (`POST /api/auth/passkey/register/verify`)
   - Verifies the newly created credential
   - Stores credential in database

3. **Authentication Challenge** (`POST /api/auth/passkey/auth/challenge`)
   - Generates a challenge for authentication
   - Returns PublicKeyCredentialRequestOptions

4. **Authentication Verification** (`POST /api/auth/passkey/auth/verify`)
   - Verifies the authentication signature
   - Creates user session on success

5. **Credential Management** 
   - List user's registered passkeys
   - Delete/revoke passkeys
   - Rename passkeys

#### Implementation Example

```python
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json
)

@app.route('/api/auth/passkey/register/challenge', methods=['POST'])
def passkey_register_challenge():
    # Must be authenticated already to register a passkey
    if 'user' not in session:
        return jsonify(error="Must be logged in to register a passkey"), 401
    
    user_id = session['user']
    
    # Generate registration options
    options = generate_registration_options(
        rp_id="your-domain.com",  # Replace with actual domain
        rp_name="Librarrarian",
        user_id=user_id.encode(),
        user_name=user_id,
        user_display_name=user_id
    )
    
    # Store challenge in session for verification
    session['passkey_challenge'] = options.challenge
    
    return jsonify(options_to_json(options))

@app.route('/api/auth/passkey/register/verify', methods=['POST'])
def passkey_register_verify():
    if 'user' not in session or 'passkey_challenge' not in session:
        return jsonify(error="Invalid session"), 401
    
    # Verify the credential
    try:
        credential = verify_registration_response(
            credential=request.json,
            expected_challenge=session['passkey_challenge'],
            expected_origin="https://your-domain.com",  # Replace
            expected_rp_id="your-domain.com"
        )
        
        # Store credential in database
        # ... database code ...
        
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400
```

### 4. Frontend Implementation

The login page would need JavaScript to interact with the WebAuthn API:

```html
<!-- In login.html -->
<button id="register-passkey-btn" class="btn btn-outline-info">
    <span class="mdi mdi-fingerprint"></span> Register a Passkey
</button>

<script>
// Registration flow
document.getElementById('register-passkey-btn').addEventListener('click', async () => {
    // Get challenge from server
    const optionsResponse = await fetch('/api/auth/passkey/register/challenge', {
        method: 'POST'
    });
    const options = await optionsResponse.json();
    
    // Convert base64url to ArrayBuffer
    options.challenge = base64urlToBuffer(options.challenge);
    options.user.id = base64urlToBuffer(options.user.id);
    
    // Create credential
    const credential = await navigator.credentials.create({
        publicKey: options
    });
    
    // Convert credential to JSON format
    const credentialJSON = {
        id: credential.id,
        rawId: bufferToBase64url(credential.rawId),
        response: {
            attestationObject: bufferToBase64url(credential.response.attestationObject),
            clientDataJSON: bufferToBase64url(credential.response.clientDataJSON)
        },
        type: credential.type
    };
    
    // Send to server for verification
    await fetch('/api/auth/passkey/register/verify', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(credentialJSON)
    });
});

// Helper functions for base64url encoding/decoding
function base64urlToBuffer(base64url) {
    const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/');
    const binary = atob(base64);
    return Uint8Array.from(binary, c => c.charCodeAt(0));
}

function bufferToBase64url(buffer) {
    const binary = String.fromCharCode(...new Uint8Array(buffer));
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}
</script>
```

### 5. Environment Variables

Add to `.env.example`:
```env
# --- Passkey Authentication (Optional) ---
# Enable passkey/WebAuthn authentication
PASSKEY_ENABLED=false

# The RP ID must match your domain (e.g., example.com)
# For localhost development, use "localhost"
WEBAUTHN_RP_ID=localhost

# The origin must match your full URL including protocol
# For localhost: http://localhost:5000
# For production: https://your-domain.com
WEBAUTHN_ORIGIN=http://localhost:5000
```

### 6. Security Considerations

1. **HTTPS Only**: Passkeys require HTTPS in production
2. **Challenge Expiry**: Challenges should expire after a short time (e.g., 5 minutes)
3. **Counter Validation**: Check signature counter to detect cloned authenticators
4. **User Verification**: Consider requiring user verification for sensitive operations
5. **Backup**: Users should have multiple authentication methods (username/password, OIDC, AND passkey)

### 7. User Experience Flow

#### Registration Flow
1. User logs in with existing method (password or OIDC)
2. User navigates to account settings
3. User clicks "Register a Passkey"
4. Browser prompts for biometric/security key
5. Passkey is saved and can be used for future logins

#### Login Flow
1. User clicks "Login with Passkey" on login page
2. Browser prompts for biometric/security key
3. User authenticates with their device
4. User is logged in to the dashboard

### 8. Testing

- Test with multiple authenticator types (platform, cross-platform)
- Test credential management (rename, delete)
- Test error cases (cancelled authentication, timeout, etc.)
- Test with different browsers (Chrome, Firefox, Safari, Edge)

## Implementation Effort

This is a **significant feature** that would require:
- ~8-12 hours of development time
- Thorough security review
- Comprehensive testing
- Documentation updates
- Migration path for existing users

## Alternative: WebAuthn Library

Consider using a complete WebAuthn library like [py_webauthn](https://github.com/duo-labs/py_webauthn) which handles much of the complexity.

## Recommendation

Implement this as a **separate feature PR** after the current bug fixes are complete. It should not be bundled with bug fixes due to its complexity and scope.
