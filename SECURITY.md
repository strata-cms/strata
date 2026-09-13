# Security Policy

Do not report suspected vulnerabilities in public issues if disclosure could put deployed users at risk. Use the repository owner's private security reporting channel once the repository is hosted.

For implementation requirements, see `docs/ai/security.md`.

Security-sensitive changes require explicit review plus:

```bash
make check
make security
```

CI additionally performs CodeQL analysis, dependency review on pull requests, and Trivy scanning of the built container. These checks are complementary; none replaces threat-aware code review.

The Management API and generic Unfold editor are privileged surfaces. Access
requires Django staff status plus the Django permission mapped to the
requested action, decided once by the shared `ContentAuthorizationPolicy`
(`infrastructure/authorization/policy.py`) and enforced inside the
application use cases — not duplicated per presentation adapter. Publish
authority is a separate permission from edit authority
(`publish_contentrecord` vs `change_contentrecord`). Object/site/subtree-scoped
authorization (beyond staff + Django permission) remains unimplemented; see
`docs/adr` and `docs/ai/architecture.md` before expanding Management access
beyond trusted staff.

## OWASP framework checks

`docs/ai/security.md` maps this project's controls against the OWASP Top 10,
ASVS, LLM Top 10, and Agentic AI threat categories, and explains how to run an
OWASP-framed review on demand via the `security-reviewer` subagent (Claude) or
`security_reviewer` agent (Codex).
