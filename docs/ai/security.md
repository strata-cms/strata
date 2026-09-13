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

## Running an OWASP-framed review on demand

There is no separate OWASP skill/command by design — ask the `security-reviewer`
subagent (Claude Code) or `security_reviewer` agent (Codex) to review the
current diff or a specific area; both are instructed to read this file and
report findings tagged by OWASP Top 10 ID (and ASVS chapter, where the
finding maps to a specific control). Say e.g. "use the security-reviewer
agent to check this against OWASP Top 10" or "run an ASVS pass over the
Management API." Nothing here runs automatically in CI beyond the
already-automated subset noted in the table below — this is a manual/agent-
assisted checklist, not a scanner.

## OWASP Top 10 (2021) coverage map

Automated where a tool genuinely checks it; everything else is a manual/
agent-review responsibility using this file as the checklist. "Gap" means no
control exists yet — not that the risk is accepted, just that it is unaddressed.

| ID | Category | Coverage in this project | Status |
|----|----------|---------------------------|--------|
| A01 | Broken Access Control | `ContentAuthorizationPolicy` (`infrastructure/authorization/policy.py`) is the single decision point for every Management action, called from the application use cases (not duplicated per adapter). Publish/change/archive/restore use distinct permissions. Delivery API only ever serves the explicitly published revision. | Object-level checks exist (staff + per-action Django permission). Site/subtree/per-object scoping is a documented gap — see `docs/ai/architecture.md` and the ADRs. |
| A02 | Cryptographic Failures | No custom cryptography in the codebase. `SECRET_KEY` from environment only; production forces `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`/HSTS (opt-in via `DJANGO_SECURE_HSTS_SECONDS`). | Automated: `make security`'s `manage.py check --deploy`. |
| A03 | Injection | Django ORM only (no raw SQL in the codebase); DRF serializers validate all API input; no `shell=True`/`eval`/`exec` on untrusted content. | Partially automated: Ruff `S` (bandit-derived) rules in `make security`; SQL/template injection otherwise needs manual review since Ruff can't prove ORM-only usage. |
| A04 | Insecure Design | Data Mapper architecture (ADR 0001), immutable revision lifecycle (ADR 0002), plugin registry validation (ADR 0003), typed block trees (ADR 0004), schema-driven editor with no ModelForm write path (ADR 0005), explicit route tree (ADR 0006) — each an explicit threat-model-adjacent design decision, not an afterthought. | Design-level; verified by architecture review (`architecture-reviewer` subagent), not a scanner. |
| A05 | Security Misconfiguration | `DEBUG=False` and explicit `ALLOWED_HOSTS` enforced in `production.py` (raises `ImproperlyConfigured` if unset); security headers set explicitly. | Automated: `make security`'s Django deploy check. |
| A06 | Vulnerable and Outdated Components | `uv.lock` pinned and committed; new dependencies reviewed for maintenance/license/footprint per this doc's "Dependencies and supply chain" section. | Automated: `pip-audit --strict` in `make security` (audits the exported third-party dependency set, not the unpublished local package); CodeQL, Dependency Review, and Trivy in CI. |
| A07 | Identification and Authentication Failures | Django's built-in auth only; Management API requires staff + explicit permission; both Delivery and Management endpoints are rate-limited (`ScopedRateThrottle`, `strata-delivery`/`strata-management` scopes, tunable via `STRATA_*_THROTTLE_RATE`). | No custom login/password/token flow exists to audit yet — this project has not built one. Revisit if it does. |
| A08 | Software and Data Integrity Failures | No `pickle`/unsafe YAML on untrusted data anywhere in the codebase; `uv.lock` pins exact dependency versions; CI installs with `--locked`. | Automated: pip-audit, CodeQL. Manual: verify any future deserialization boundary against this file's "Injection and dangerous execution" section. |
| A09 | Security Logging and Monitoring Failures | Structured logging conventions exist (`docs/ai/standards.md`: never log secrets/tokens/session identifiers). The outbox (`strata.content.published`/`archived`/`restored`) is an integration-event log, not a security audit log. | **Gap**: no dedicated security-event audit trail (failed auth attempts, permission denials, admin bulk actions) beyond Django's/the web server's default request logs. Flagged, not built — would need a concrete requirement first (see Scope Discipline in `CLAUDE.md`). |
| A10 | Server-Side Request Forgery | No code path fetches a user-influenced URL server-side today. | N/A currently. This file's "SSRF / outbound network" section applies the moment any such feature (webhooks, URL preview, remote media import, etc.) is added — treat that as a mandatory trigger for a fresh review of this row. |

## OWASP ASVS (target: Level 2) — condensed checklist

ASVS has ~300 individual requirements across 14 chapters; this is a
project-scoped condensation, not the full standard — use the real ASVS
document for anything safety/compliance-critical. Level 2 (standard
verification, appropriate for most business applications handling
non-trivial data) is the working target; nothing here claims Level 3
(high-assurance) rigor.

| Chapter | Condensed checks | Status here |
|---------|-------------------|-------------|
| V1 Architecture | Trust boundaries documented; threat-relevant decisions recorded as ADRs. | Met — ADRs 0001-0006. |
| V2 Authentication | Django auth primitives; no custom credential storage/verification. | Met by default (no custom auth built). |
| V3 Session Management | Django session cookies; `SESSION_COOKIE_SECURE` in production. | Met; no custom session handling exists to audit. |
| V4 Access Control | Server-side, default-deny, object-level where content is referenced by ID. | Met at the staff+permission level; **gap** at per-object/site scope (A01 above). |
| V5 Validation, Sanitization, Encoding | DRF serializers at every API boundary; Django template auto-escaping; domain-level `RevisionData`/slug/content-type-key validation. | Met for current surfaces. |
| V6 Stored Cryptography | No custom crypto/key storage exists. | N/A currently. |
| V7 Error Handling and Logging | `_application_error` translates domain/application exceptions to stable HTTP responses without leaking internals; secrets excluded from logs per `standards.md`. | Met for current surfaces; see A09 gap for audit-log depth. |
| V8 Data Protection | No sensitive-data-at-rest requirement identified yet (no PII/payment data modeled). | Revisit if such data is added. |
| V9 Communications | HTTPS enforced in production (`SECURE_SSL_REDIRECT`, HSTS opt-in). | Met. |
| V10 Malicious Code | No `eval`/`exec`/unsafe deserialization; dependency provenance reviewed per this doc. | Met; ongoing via `make security`. |
| V11 Business Logic | Optimistic concurrency (aggregate version) prevents lost updates; archive/publish/restore invariants enforced in use cases, not presentation code. | Met. |
| V12 Files and Resources | No file upload feature exists yet. | N/A currently — this file's "Files and archives" section is the checklist the moment one is added. |
| V13 API | Versioned (`/api/v1/`), explicit permission classes, rate-limited, `drf-spectacular` schema generation is warning-free (`make schema-check`). | Met. |
| V14 Configuration | `DEBUG=False`/`ALLOWED_HOSTS` enforced; secrets from environment only; pinned lockfile; container runs from the Dockerfile's pinned base. | Met. |

## OWASP LLM Top 10 (2025) — dormant, no LLM integration exists

This project does not call an LLM or embed AI-generated-content handling
today. These categories are recorded so a reviewer checks them **the moment**
that changes (e.g. an AI-assisted content suggestion feature, an embeddings
search backend, an LLM-based content moderator) rather than discovering the
gap after the fact.

| ID | Category | Status |
|----|----------|--------|
| LLM01 | Prompt Injection | N/A — no LLM calls in the codebase. |
| LLM02 | Sensitive Information Disclosure | N/A |
| LLM03 | Supply Chain (models/datasets/plugins) | N/A |
| LLM04 | Data and Model Poisoning | N/A |
| LLM05 | Improper Output Handling | N/A |
| LLM06 | Excessive Agency | N/A |
| LLM07 | System Prompt Leakage | N/A |
| LLM08 | Vector and Embedding Weaknesses | N/A |
| LLM09 | Misinformation | N/A |
| LLM10 | Unbounded Consumption | N/A |

## OWASP Agentic AI threats — dormant, no autonomous agent integration exists

Same status as above: recorded for the day this project gives an LLM/agent
the ability to take actions (call tools, write content, trigger workflows)
rather than just being called as a service.

| Category | Status |
|----------|--------|
| Agent authorization / excessive autonomy | N/A |
| Tool/plugin misuse | N/A |
| Memory/context poisoning | N/A |
| Cascading hallucination / unchecked multi-agent trust | N/A |
| Human-in-the-loop bypass for high-impact actions | N/A |
| Identity spoofing between agents/services | N/A |

If this project ever wires an LLM into a write path (e.g. "AI-assisted
publish"), treat that as mandatory A01/A04/LLM06/Agentic-authorization
re-review before shipping it — an agent that can call `publish_content` is a
new, highly privileged actor in this system's threat model, not a UI
convenience.
