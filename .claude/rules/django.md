---
paths:
  - "src/strata_cms/**/*.py"
---
For Django/DRF changes:
- Read `docs/ai/architecture.md`; for ORM/database/cache/search/messages/tasks/
  storage/time also read `docs/ai/infrastructure.md`.
- Treat Django ORM models as persistence records, not domain entities. Active
  Record operations belong in `strata_cms.infrastructure.persistence.django`.
- Application use cases own transaction intent via Unit of Work ports; concrete
  Django UoW/repository/query adapters own `transaction.atomic()`, row locking,
  ORM expressions, QuerySets, and record mapping.
- Keep transport/admin handlers thin. API code calls application use cases or
  query-service ports; it must not directly query persistence records.
- Admin may register persistence records for framework integration, but custom
  publish/move/restore/retry/etc. actions call application use cases.
- Core publication/revision/tree workflows must not be implemented through
  signals or duplicated between Admin/API/CLI/worker.
- Use migrations for schema changes and database constraints for durable
  persistence invariants where possible.
- External side effects required after a DB commit use reliable post-commit/
  outbox semantics where loss matters; do not assume DB + broker atomicity.
- Explicitly validate serializer/form fields and permissions; never rely on
  client/UI state for authorization.
- Management writes require object-level authorization and lost-update
  protection for revisioned state; Delivery endpoints expose published state
  only except explicitly authorized preview.
- Avoid N+1 queries inside query/persistence adapters and accidental public-field
  exposure.
- Unfold admin classes inherit from matching Unfold classes.
- Public API changes need tests and accurate drf-spectacular annotations;
  `make schema-check` stays warning-free.
