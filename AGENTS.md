# Strata — Codex Repository Instructions

Repository-wide rules for the Python 3.12–3.14 / Django 5.2 LTS Strata.
Python 3.14 is the default runtime. Django ORM is persistence infrastructure,
not the domain model.

## Required reading
Before implementation/review read `docs/ai/standards.md` plus:
- `docs/ai/architecture.md` for domain/model/plugin/API architecture;
- `docs/plugins.md` when implementing or reviewing a plugin/content type;
- `docs/ai/infrastructure.md` for database/cache/search/messaging/tasks/storage/time;
- `docs/ai/security.md` for security-sensitive work;
- `docs/ai/tooling.md` for dependency/CI/build/tool changes.

## Core architecture rules
- Headless-first modular monolith; explicit typed plugin API; immutable
  revisions; strict draft/published isolation.
- Core lifecycle model is stable `Content` identity + append-only `Revision`
  snapshots; Content aggregate state is immutable, with independent latest/draft and
  published pointers. See ADR 0002.
- Code-defined content types/extensions + versioned structured blocks; no
  runtime model builder.
- Stable UUID identities and namespaced persisted keys; no foundational
  `GenericForeignKey`/database-local `ContentType` identity.
- Page is a content capability, not the universal content base.
- Business use cases/transactions live in application services reused by
  admin/API/CLI/worker; signals are notifications, not workflow orchestration.
- Plugin lifecycle follows ADR 0003: startup-only `StrataRegistryBuilder` →
  dependency/version/API validation → deterministic immutable `StrataRegistry`.
  Django plugin apps expose `StrataPluginConfig`; callbacks receive an owner-scoped
  `PluginRegistrar`, not the raw builder, and `AppConfig.ready()` is not a global
  registry mutation bus.
- Third-party plugins import `strata_cms.plugin_api`. Content types own typed
  schemas and complete pure adjacent migration chains. Historical revisions
  migrate in memory; new writes normalize to current schema through the
  application `ContentTypeService` port.
- Structured blocks follow ADR 0004. Blocks are immutable values inside
  revisions with stable UUID/type/version/data/named slots. Strata owns
  tree/envelope semantics; block schemas own only typed `data`. Recursively
  enforce slot/type/cardinality/depth constraints and preserve block IDs when
  normalizing new revisions.
- Explicit cross-plugin block references require declared plugin dependencies.
  Do not create mutable ORM rows for editorial blocks or hide child trees inside
  plugin-specific block data.
- Delivery API serves published revisions only; Management API owns authorized
  draft/write operations with optimistic concurrency protection.
- Management editing follows ADR 0005. Editor metadata is a presentation-neutral
  hint layer, never the validation authority. Admin/external clients edit
  ephemeral working documents and persist only through content/revision use
  cases; do not create a ModelForm/record-mutation or mutable draft-row shortcut.
- Generic editor discovery goes through the application `EditorCatalog` port;
  presentation adapters must not depend directly on registry internals.
- Projections/search/cache are rebuildable from authoritative state.

## Data Mapper / persistence rules
- Domain entities are plain Python. Domain/application code must not use Django
  Active Record APIs.
- Django ORM classes are persistence records, preferably `*Record`, under
  `strata_cms.infrastructure.persistence.django`.
- Outside that adapter, do not implement application behavior with
  `Model.objects`, QuerySets, `.save()`, `.delete()`, DB connections,
  `transaction.atomic()`, ORM expressions/lookups, or raw SQL.
- Domain imports no Django/DRF/application/infrastructure modules.
- Application imports domain + application-owned ports, never Django/DRF or
  concrete infrastructure. `make architecture-check` enforces import contracts.
- Repository interfaces return entities, not records/QuerySets. Concrete
  repositories + entity↔record mappers are infrastructure.
- Application use cases own transaction intent through Unit of Work ports;
  Django UoW implementations own `transaction.atomic()`.
- Content writes use expected aggregate versions/compare-and-swap; the Django
  write UoW may additionally lock aggregate rows to serialize revision-number
  allocation. Do not turn this into last-write-wins behavior.
- Read paths may use query-service ports returning immutable DTOs with optimized
  ORM/SQL implementations in infrastructure; do not force all reads through
  entities or leak provider query syntax.
- Admin may register records for framework integration, but custom business
  actions call application services rather than duplicating workflows.

## Infrastructure capability rules
- Use narrow CMS-owned ports for Clock, cache, search, events, tasks, durable
  messaging, storage and persistence.
- Defaults should require only Django/PostgreSQL/storage where practical.
  Redis, Celery, RabbitMQ, Kafka, OpenSearch, etc. are optional adapters.
- Events state facts; tasks request work; brokers transport messages. Do not
  treat Celery and RabbitMQ as interchangeable.
- Durable delivery is at-least-once; handlers are idempotent. Use a
  transactional outbox for integration events that must survive DB commit.
- Target simple async default: optional PostgreSQL-backed durable queue and
  separate `strata_worker` process using the same image, with retry/lease/dead
  letter behavior; the web process must not require the worker.
- Inject Clock for time-dependent application behavior.

## Engineering/security rules
- uv only; Ruff is formatter/import/lint/security heuristic tool; mypy is the
  canonical type checker; Import Linter owns dependency boundaries.
- Follow PEP 8/257, Python Guide, OpenSSF, OWASP and Django security guidance.
- Type public/reusable interfaces; no unexplained `Any`, broad casts/ignores.
- Validate trust boundaries and object-level authorization. Explicit serializer
  fields; no string-built SQL, unsafe deserialization, `eval`/`exec`, or unsafe
  subprocess shell use.
- Never hard-code/expose secrets or read `.env`/secret files without request.
- Public API stays under `/api/v1/`; OpenAPI remains warning-free.
- Schema changes require migrations; never rewrite applied migrations just to
  satisfy tests.
- Do not weaken quality/security/architecture configuration to make code pass.

## Canonical commands
```bash
make bootstrap
make install
make format
make architecture-check
make check
make security
make test
make test-fast
make schema-check
make package-build
make docker-build
```

Run focused checks while iterating, then `make check`. For security/API/build
changes run the relevant additional gates. Never claim a check passed unless it
actually ran.

## Testing expectations
- Domain tests normally require no Django database.
- Application behavior should use fakes for repositories/UoW/ports when useful.
- DB integration tests focus on record mappings, repository/query adapters,
  transactions/locking/migrations and Django admin/framework behavior.
- Bug fixes get regression tests when practical; new behavior covers success,
  invalid input, permissions and meaningful edges.
- Tests are deterministic/network-independent; Hypothesis is selective.
- >=85% coverage is a backstop, not the engineering objective.

## Agent workflows / review
- Codex skills: `.agents/skills/$review`, `$quality`, `$fix`.
- Read-only specialists: `.codex/agents/`.
- Parallelize independent review, not overlapping write-heavy changes.

Review priority: security; correctness/integrity/concurrency; persistence and
transaction boundaries; API/schema/migration/plugin compatibility; reliability;
query behavior/performance; typing/tests. Skip Ruff-owned cosmetics.
