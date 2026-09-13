---
paths:
  - "src/strata_cms/**/*.py"
  - "tests/**/*.py"
---
`docs/ai/architecture.md` is normative. For persistence/cache/search/messages/
tasks/storage/time also read `docs/ai/infrastructure.md`.

Critical invariants:
- modular monolith; domain/application depend inward, not on presentation or
  concrete infrastructure;
- Django ORM is persistence infrastructure only: records (`*Record`), QuerySet,
  `.objects`, `.save()`, `.delete()`, DB connections and `transaction.atomic()`
  stay in `strata_cms.infrastructure.persistence.django` except framework-owned
  Admin mechanics;
- domain entities are plain Python; repositories return entities, not records;
- application use cases own transaction intent through Unit of Work ports;
- read query services return DTOs/projections and hide ORM/provider syntax;
- stable UUID identities/namespaced persisted keys; no foundational
  GenericForeignKey/ContentType-ID coupling;
- immutable versioned revisions; draft state is isolated from published state;
- core lifecycle follows ADR 0002: `Content.latest_revision_id` is draft state,
  `Content.published_revision_id` is delivery state; new revisions never publish
  implicitly;
- content write commands carry expected aggregate versions; Django write UoWs
  may lock aggregate rows to serialize revision numbering while repositories
  retain compare-and-swap updates;
- publish/restore/move/retry workflows are shared use cases, not signals/admin
  or API-specific implementations;
- plugin lifecycle follows ADR 0003: startup builder → dependency/version/API
  validation → immutable registry; plugin callbacks receive owner-scoped
  `PluginRegistrar`, not the raw builder; Django `ready()` must not mutate a
  global registry; third-party code imports `strata_cms.plugin_api`;
- content schemas are typed and versioned; migration chains are pure, adjacent
  and complete; old revisions migrate in memory while new writes normalize to
  current schema through the application port;
- persisted block/revision/message schemas require explicit versioning and
  compatibility/migration paths;
- Delivery API is published/read-oriented; Management API owns authorized writes
  and lost-update protection;
- ADR 0005 management editing is schema-driven but schema validation remains
  server-side; Admin/Management clients edit ephemeral working documents and
  persist via content/revision use cases, never ModelForm/record mutation;
- generic editor metadata is presentation-neutral; block constraints come from
  semantic block definitions, not duplicated UI-only rules;
- cache/search/routes are rebuildable projections;
- cache/search/events/tasks/message transport/storage/clock are narrow ports;
  external providers stay optional;
- events != tasks != brokers; durable delivery is at-least-once and handlers
  must be idempotent; reliable external publication uses an outbox;
- do not introduce mandatory Redis/Celery/RabbitMQ/Kafka/search/microservices
  without a concrete requirement.

`make architecture-check` must pass. Do not add Import Linter ignores or move
imports merely to conceal a broken dependency; fix the boundary.


## Structured blocks
- Follow ADR 0004. Blocks are immutable values inside revision JSON, never
  mutable Django models.
- Preserve stable block UUIDs across edits/new revisions of the same logical
  block; block data schema versions migrate independently from content schemas.
- Use CMS-owned named slots for nesting. Do not hide child block trees inside
  plugin-specific `data`.
- Enforce declared slot/root cardinality, allowed block types, nesting depth and
  cross-plugin dependency declarations through the registry.
- New writes normalize block trees to current schemas; historical revisions are
  never mass-rewritten during plugin upgrades.
