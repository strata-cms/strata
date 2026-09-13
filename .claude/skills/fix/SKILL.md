---
name: fix
description: Reproduce, diagnose, fix, and verify a bug or failing check without violating Strata architecture invariants.
---
1. Read repository instructions and relevant standards; read `docs/ai/architecture.md` for domain/model/plugin/API behavior and `docs/ai/infrastructure.md` for persistence/cache/search/messaging/tasks/storage/time.
2. Reproduce the issue with the narrowest reliable command/test before editing when practical.
3. Trace the root cause across entity/record mapping, repository/UoW/query, service, revision/publication, plugin, API/admin, and infrastructure-port boundaries; do not patch only the visible symptom when the invariant is broken elsewhere.
4. Preserve draft/published isolation, historical revision readability, authorization, transaction/concurrency semantics, and public plugin/API compatibility.
5. Add/update a regression test that fails for the old behavior and validates the intended behavior when practical.
6. Make the smallest maintainable fix. Do not bypass repositories/UoW/services with Active Record calls, add provider SDKs to domain/application code, hide workflow in signals, weaken architecture checks, or add mandatory infrastructure as a shortcut.
7. Re-run the focused reproduction/test, then `make check`.
8. Also run `make security` for security/dependency fixes, `make schema-check` for API fixes, and `make docker-build` for runtime/container fixes.
9. Summarize root cause, violated/preserved invariant, fix, verification, and residual risk.
