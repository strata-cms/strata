# Security Requirements

Use this as a practical project checklist together with the OpenSSF Secure Coding Guide for Python, OWASP Top 10/API guidance, OWASP Django Security Cheat Sheet, and Django security documentation.

## Trust boundaries
Treat all HTTP input, headers, cookies, uploaded files, remote API data, admin-entered rich text, environment variables, database content originating from users, and job/message payloads as untrusted unless proven otherwise. Canonicalize before validation where applicable and prefer allowlists.

## Authentication and authorization
- Use Django authentication primitives unless requirements explicitly justify another system.
- Enforce authorization server-side for every protected operation.
- Check object-level permissions whenever users can reference other objects by identifier.
- Default-deny sensitive actions.
- Do not infer authorization from UI visibility, client-provided roles, serializer omission, URL obscurity, or possession of an object ID.
- Rate-limit/protect high-risk endpoints such as login, reset, token issuance, and expensive operations when those features are introduced.

## Secrets and configuration
- Secrets come from environment variables or a dedicated secrets manager.
- Never commit `.env`, credentials, certificates/private keys, DB dumps/backups, or tokens.
- Use a long random Django `SECRET_KEY`; rotate compromised credentials.
- Production uses `DEBUG=False` and explicit `ALLOWED_HOSTS`.

## HTTP / Django production hardening
Production configuration must deliberately address:
- HTTPS redirect/trusted edge behavior;
- `SECURE_PROXY_SSL_HEADER` only for a trusted proxy that overwrites the header;
- `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE`;
- HttpOnly/SameSite choices appropriate to the auth model;
- HSTS only after HTTPS is verified end-to-end;
- content-type sniffing, frame policy, referrer policy, and relevant browser isolation headers;
- CSP when templates/admin customization introduces executable or rich user content;
- CSRF protection for browser/session-authenticated state changes.

`make security` runs Django's deployment checks using safe CI placeholders. Do not suppress deployment warnings without understanding the deployment topology.

## Injection and dangerous execution
- ORM/query parameters only; no SQL string concatenation/interpolation.
- Do not construct shell commands from untrusted strings. Prefer `subprocess.run([...], shell=False, check=True)`.
- No `eval`/`exec` on external content.
- No unsafe YAML loaders or pickle for untrusted data.
- Escape HTML by default. Avoid `mark_safe`/`safe` for user-controlled text.
- Treat template names, headers, filenames, and redirect destinations as injection-capable boundaries.

## Files and archives
- Validate size, authorization, expected extension, and MIME/content where practical.
- Generate server-side storage names; never trust client paths.
- Store uploads away from executable/template paths.
- Serve untrusted uploads with safe content disposition/types and preferably from a separate origin/object store.
- Prevent path traversal and archive extraction outside the intended directory.
- Consider decompression bombs, image/parser limits, and malicious file formats.

## SSRF / outbound network
- If users influence URLs, validate scheme/host/port and apply an allowlist where possible.
- Block link-local, loopback, private/internal metadata destinations unless explicitly required.
- Revalidate redirect targets and DNS-derived destinations for high-risk fetchers.
- Set connect/read timeouts plus response-size limits.

## Redirects
Use local named URLs or validated allowlisted destinations. Never blindly redirect to a user-provided URL.

## API
- HTTPS only in production.
- Explicit authentication/permission classes.
- Explicit parsers/renderers/content types for sensitive endpoints.
- Pagination and request/body size limits.
- Avoid verbose internal exceptions in responses.
- Never put API keys/tokens in URLs.
- Use semantic HTTP status codes.
- Treat the generated OpenAPI schema as public attack-surface documentation: it must be accurate and must not unintentionally expose internal-only operations.

## Dependencies and supply chain
- Commit `uv.lock` after real package-index resolution; do not fabricate or hand-edit it.
- Review new dependencies for maintenance, license, provenance, transitive footprint, and security history.
- Local security checks use Ruff `S`, pip-audit, and Django deployment checks.
- CI additionally uses CodeQL, Dependency Review, and Trivy.
- Build containers from supported pinned-major runtimes and run as non-root.
- Keep build tooling out of the final image where practical.
- Prefer immutable deployment artifacts; never install packages into a running production container.

## Logging/privacy
Never log credentials, reset links/tokens, Authorization headers, session cookies, secret keys, payment secrets, or unnecessary personal data. Sanitize untrusted values if logs feed terminals/SIEMs.

## Security review triggers
Perform an explicit security review for changes touching authentication/authorization, file handling, HTML/rich text/templates, SQL/raw queries, subprocesses, serialization, redirects/outbound HTTP/webhooks, secrets/configuration, admin bulk actions, cryptography, CORS/CSRF/cookies/session policy, dependency additions, or deployment/container configuration.
