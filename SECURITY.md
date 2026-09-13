# Security Policy

Do not report suspected vulnerabilities in public issues if disclosure could put deployed users at risk. Use the repository owner's private security reporting channel once the repository is hosted.

For implementation requirements, see `docs/ai/security.md`.

Security-sensitive changes require explicit review plus:

```bash
make check
make security
```

CI additionally performs CodeQL analysis, dependency review on pull requests, and Trivy scanning of the built container. These checks are complementary; none replaces threat-aware code review.

The Management API and generic Unfold editor are privileged surfaces. The
initial implementation requires Django staff access plus explicit view/add/change permissions, uses normal Django/DRF
session authentication and CSRF protection for Admin-originated writes, and
retains optimistic concurrency checks. Do not weaken these checks in client
code. Finer object/site/subtree authorization should be implemented through an
explicit policy boundary before exposing Management access beyond trusted staff.
