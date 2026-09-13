---
name: quality
description: Run and interpret Strata quality and architecture gates after implementation or before a PR.
---
Before completion run `make check`; run the smallest relevant checks first during iteration.

For architecture-affecting changes, manually verify against `docs/ai/architecture.md` and, when relevant, `docs/ai/infrastructure.md`:
- dependency direction/import contracts and public plugin boundaries;
- no Django ORM/record leakage into domain/application/API;
- entity↔record mapping, repositories, Unit of Work and query-service boundaries;
- immutable revision and draft/published isolation;
- service-layer ownership of business workflows;
- transaction/concurrency safety;
- persisted schema-version compatibility;
- published projection rebuildability;
- at-least-once/idempotent messaging and optional-provider isolation;
- Delivery vs Management API separation.

Use additional executable gates when relevant:
- security-sensitive or dependency changes: `make security`;
- API changes: `make schema-check` and inspect externally visible OpenAPI changes;
- package/build metadata changes: `make package-build`;
- Docker/runtime changes: `make docker-build`.

`make check` includes Import Linter and is authoritative for executable completion, but it does not replace semantic architectural review. Do not weaken configuration to make a patch pass. Re-run focused failures and then the canonical gate. Summarize exactly what ran, final status, and any architecture checks that remain manual.
