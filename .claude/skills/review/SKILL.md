---
name: review
description: Perform a repository-aware review of current changes, including CMS architecture invariants and quality gates.
---
1. Read the repository instructions and `docs/ai/standards.md`; for domain/model/plugin/API changes also read `docs/ai/architecture.md`; for persistence/cache/search/messaging/tasks/storage/time read `docs/ai/infrastructure.md`; for security-sensitive work read `docs/ai/security.md`.
2. Inspect `git status`, the relevant diff, surrounding implementation, migrations, and tests.
3. Check architecture invariants: dependency direction, Django ORM/record leakage, entity↔record mapping, repository/UoW/query boundaries, service-layer ownership, immutable revision/published-state isolation, plugin API boundaries, content/block schema-version compatibility, structured-block slot/dependency invariants, ADR 0005 editor-metadata/schema separation and Admin/Management single-write-path behavior, authorization, transactions/concurrency, at-least-once/idempotent messaging, optional-provider isolation, and rebuildability of projections.
4. Run focused tests/static checks where useful.
5. Report findings ordered by severity with file/line references, impact/failure scenario, and the smallest maintainable fix.
6. Do not report Ruff-owned cosmetics. If there are no material findings, say so and list residual risks/test gaps/unverified architecture assumptions.
