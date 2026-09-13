---
paths:
  - "src/**/*.py"
  - "Dockerfile"
  - "docker-compose.yml"
  - ".github/workflows/*.yml"
---
Treat security-sensitive work according to `docs/ai/security.md`. Pay special attention to authentication/authorization, uploads, HTML, SQL, subprocesses, deserialization, redirects, outbound HTTP, secrets, admin actions, cookies/CSRF/CORS, and dependency changes.

Never weaken security checks to make a patch pass. Run `make security` for changes in these areas when the environment allows it.
