---
paths:
  - "src/**/*.py"
  - "tests/**/*.py"
  - "manage.py"
---
For Python changes, enforce `docs/ai/standards.md` and the repository Ruff/mypy configuration.

Critical reminders:
- PEP 8/257; Ruff owns formatting, imports, linting, modernization, and fast security checks.
- mypy is the canonical type checker; do not paper over failures with broad `Any`, casts, or ignores.
- Prefer explicit Django patterns and small cohesive modules.
- No wildcard imports except the conventional split-settings modules already present.
- No bare exceptions, hidden I/O, mutable defaults, unsafe dynamic execution, or unexplained broad suppressions.
- Run focused tests while iterating and `make check` before completion.
