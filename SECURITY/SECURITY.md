# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Librarrarian, please report it by creating a private security advisory on GitHub or by contacting the maintainers directly. Please do not open public issues for security vulnerabilities.

## Security Best Practices

### 1. Authentication & Authorization

- **Always enable authentication in production** by setting `AUTH_ENABLED=true` in your `.env` file
- Use strong, randomly generated values for:
  - `FLASK_SECRET_KEY` (use `openssl rand -hex 32`)
  - `API_KEY` (use `openssl rand -hex 32`)
  - `DB_PASSWORD` (use a strong password)
- Use OIDC integration for enterprise environments when possible
- Change default credentials immediately after deployment

### 2. SSL/TLS Configuration

- **Production deployments MUST use SSL certificate verification**
- Only disable SSL verification (`ARR_SSL_VERIFY=false`) in development with self-signed certificates
- Never disable SSL verification in production environments
- Consider using a reverse proxy (like nginx or Traefik) with valid SSL certificates

### 3. Database Security

- Use strong, unique passwords for database credentials
- Do not expose the PostgreSQL port (5432) to the public internet
- Regularly backup your database
- The database user should only have necessary permissions

### 4. Network Security

- Run the application behind a reverse proxy with rate limiting
- Do not expose the application directly to the internet without additional protection
- Use firewall rules to restrict access to trusted networks when possible
- Consider using a VPN for remote access

### 5. File System Security

- Ensure the application has minimal file system permissions
- Media files should be read-only from the application's perspective
- Use dedicated backup directories with appropriate permissions
- Regularly audit file access logs

### 6. Container Security

- Keep Docker images up to date
- Use the latest stable versions of the application
- Do not run containers as root
- Use Docker secrets for sensitive data instead of environment variables when possible
- Regularly scan images for vulnerabilities

### 7. API Security

- Protect the API with authentication (API keys for workers)
- Implement rate limiting on API endpoints
- Validate and sanitize all inputs
- Use HTTPS for all API communications in production

### 8. Logging & Monitoring

- Regularly review application logs for suspicious activity
- Do not log sensitive information (passwords, API keys, tokens)
- Set up alerts for authentication failures
- Monitor for unusual file access patterns

## Security Features Implemented

### Input Validation
- File paths are validated to prevent path traversal attacks
- Database identifiers are validated to prevent SQL injection
- User inputs are sanitized before processing

### SQL Injection Prevention
- Parameterized queries are used throughout the application
- Database user names are validated before use in dynamic SQL

### SSL/TLS Support
- Configurable SSL certificate verification for external API calls
- OIDC SSL verification can be configured separately

### Authentication
- Multi-layered authentication (OIDC, Local, API Keys)
- Session-based authentication for web UI
- API key authentication for worker nodes
- Dev mode bypass for local development only

### Secure Headers
- The application uses Flask security best practices
- ProxyFix middleware for proper handling behind reverse proxies

## Known Limitations

### CSRF Protection
The application currently does not implement CSRF (Cross-Site Request Forgery) protection tokens. This is partially mitigated by:
- Session-based authentication required for all state-changing operations
- API key authentication for worker communications
- The application being designed for trusted, internal use

**Recommendation**: Deploy behind a reverse proxy that implements CSRF protection, or use a Same-Site cookie policy to mitigate CSRF risks.

### Self-Signed Certificates
The application can be configured to work with self-signed certificates by setting `ARR_SSL_VERIFY=false` and `OIDC_SSL_VERIFY=false`. This should **only** be used in development or trusted internal networks, never in production.

### Base64 Password Encoding
The local login password is base64-encoded, which is encoding, not encryption. This is only intended for basic obfuscation in the configuration file. For production use, OIDC authentication is strongly recommended.

### File System Access
The application requires read/write access to media directories for transcoding. Ensure proper file system permissions are set to prevent unauthorized access.

### Rate Limiting
The application does not implement rate limiting on authentication attempts or API endpoints. Consider deploying behind a reverse proxy (like nginx or Traefik) that implements rate limiting to prevent brute force attacks.

### Debug Logging
The Docker container runs Gunicorn with `--log-level debug` which may expose sensitive information in logs. In production environments with strict security requirements, consider modifying the Dockerfile to use `--log-level info` or `--log-level warning`.

## Security Updates

Security updates are released as soon as possible after vulnerabilities are discovered. Always update to the latest version to ensure you have the latest security patches.

To update:
```bash
docker-compose pull
docker-compose up -d
```

## Compliance

Librarrarian is designed for personal and small-scale use. For enterprise deployments or environments with specific compliance requirements (GDPR, HIPAA, etc.), additional security measures may be necessary.
