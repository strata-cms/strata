# Strata — Claude Code Instructions

## Mission
Build and maintain a secure, extensible, headless-first CMS in Django with an
Unfold admin. Django is the web/admin framework; Django ORM is a persistence
adapter, **not** the domain model.

## Required stack
- Python 3.12–3.14 supported; Python 3.14 default runtime/container.
- Django 5.2 LTS, Django REST Framework, django-unfold, drf-spectacular.
- PostgreSQL in production; SQLite only for lightweight local/test behavior.
- uv, Ruff, mypy + Django/DRF stubs, pytest + pytest-django.
- Import Linter for executable dependency boundaries.
- Gunicorn for production WSGI.

## Required reading
Before implementation/review read `docs/ai/standards.md` and:
- domain/model/plugin/API/architecture work: `docs/ai/architecture.md`;
- plugin implementation/extension examples: `docs/plugins.md`;
- database/cache/search/messages/tasks/storage/time work:
  `docs/ai/infrastructure.md`;
- security-sensitive work: `docs/ai/security.md`;
- dependencies/tooling/CI/builds: `docs/ai/tooling.md`.

Inspect surrounding code/tests before changing architecture. Do not invent
requirements or silently replace documented architecture with a familiar
framework shortcut.

## Architecture invariants
- Headless-first modular monolith with explicit, typed, stable plugin contracts.
- Generic behavior comes from code-defined content types/extensions and
  versioned structured blocks, not runtime-created Django models.
- Stable UUID content identities and namespaced persisted keys. Do not build
  durable CMS relationships around Django `ContentType` integers or
  `GenericForeignKey`.
- Page is one content capability, not the universal content superclass.
- Revisions are immutable/versioned. Draft state is isolated from the explicit
  published revision; Delivery API never leaks draft state.
- Core lifecycle model: stable `Content` identity + append-only `Revision`
  snapshots; Content aggregate state is immutable and lifecycle operations return new
  state. Latest revision is draft state, published revision is delivery state.
  Creating a revision never republishes implicitly. See ADR 0002.
- Publish/restore/move/retry and other business use cases live once in
  application services shared by admin/API/CLI/worker.
- Signals are notifications/integration hooks, not hidden workflow engines.
- Plugin registration follows ADR 0003: `StrataRegistryBuilder` is startup-only;
  successful compilation produces an immutable `StrataRegistry`. Django plugin
  apps expose `StrataPluginConfig` registrations and receive an owner-scoped
  `PluginRegistrar`; do not mutate a global registry from `AppConfig.ready()` or
  hand plugin callbacks the raw registry builder.
- Third-party plugins import supported contracts from `strata_cms.plugin_api`;
  do not expose/import private internals as an accidental plugin API.
- Content types own typed schemas plus complete pure adjacent migration chains.
  Historical revisions migrate in memory; never rewrite history automatically
  during plugin upgrades. New writes normalize to the current schema through
  the application `ContentTypeService` port.
- Structured blocks follow ADR 0004: immutable revision-embedded envelopes with
  stable UUID/type/version/data/named slots. Block schemas own `data`; CMS owns
  tree structure. New writes recursively normalize block schemas while
  preserving IDs; slot/type/cardinality/depth constraints are enforced.
- Cross-plugin block references require declared plugin dependencies. Do not
  hide child trees in arbitrary block data or create mutable ORM block rows.
- Management editing follows ADR 0005: optional editor metadata is
  presentation-neutral and never replaces content/block schema validation. Admin
  and external clients edit ephemeral working documents and persist only via the
  existing content/revision use cases; never introduce `ModelForm.save()` or a
  mutable server-side draft/block-row workflow as an alternate CMS write path.
- Persisted block/revision/message schemas require explicit versioning and
  compatibility/migration strategy.
- Published routes/search/cache are rebuildable projections of authoritative
  state.
- Delivery and Management APIs have different trust/state semantics;
  Management writes require object authorization and lost-update protection.
- Generic editor discovery comes from the application `EditorCatalog` port;
  presentation code must not depend directly on plugin registry internals.

## Persistence and infrastructure invariants
`docs/ai/infrastructure.md` is normative.

- Domain entities are plain Python and persistence-ignorant. Meaningful entity
  methods are fine; persistence methods are not.
- Django `models.Model` classes are persistence **records**, preferably named
  `*Record`, and belong under the Django persistence adapter.
- Outside `strata_cms.infrastructure.persistence.django`, do not use
  `Model.objects`, QuerySets, `.save()`, `.delete()`, `transaction.atomic()`,
  database connections, or ORM lookup objects to implement application logic.
- Domain code imports no Django/DRF/application/infrastructure code.
- Application code imports domain + application ports, not Django/DRF or
  concrete infrastructure. Import Linter enforces these boundaries.
- Repository interfaces return entities, never records/QuerySets/provider DSLs.
  Concrete repositories and entity↔record mappers live in infrastructure.
- Application use cases own transaction intent through Unit of Work ports;
  Django implementations use `transaction.atomic()` internally.
- Content writes use expected aggregate versions/compare-and-swap; the Django
  write UoW may additionally lock aggregate rows to serialize revision-number
  allocation. Do not turn this into last-write-wins behavior.
- Read-heavy paths may use query-service ports returning immutable DTOs instead
  of hydrating entities; ORM/query optimization remains in infrastructure.
- Django Admin may register records because the framework requires them, but
  custom business actions call application services rather than implementing a
  second Active Record workflow.
- Infrastructure uses narrow ports. Default implementations should work with
  Django/PostgreSQL/storage wherever practical; Redis/Celery/RabbitMQ/Kafka/
  OpenSearch/etc. remain optional adapters.
- Keep events, tasks, and broker/queue transport distinct. Celery is a task
  framework; RabbitMQ is a broker.
- Durable messages are at-least-once; handlers must be idempotent. Reliable
  external events use a transactional outbox with authoritative DB writes.
- Intended simple async default: optional PostgreSQL-backed durable queue plus
  `strata_worker` using the same image; no worker/broker is required merely to run
  the web application.
- Inject a Clock for time-dependent application behavior.

## Python / Django / DRF rules
- Follow PEP 8/257, Python Guide style, repository Ruff configuration, OpenSSF,
  OWASP, and Django security guidance.
- Type public/reusable interfaces. Do not suppress typing with broad `Any`,
  `cast()`, or `# type: ignore` without a concrete justification.
- Prefer small cohesive functions, explicit control flow, dataclasses/enums and
  stdlib solutions where appropriate. No mutable defaults, bare `except`,
  swallowed exceptions, hidden I/O, `eval`/`exec`, or unsafe deserialization.
- Validate untrusted input at boundaries and enforce domain invariants
  server-side. Authorization is server-side and object-level where applicable.
- Explicitly declare serializer/form exposed fields; avoid accidental
  `fields = "__all__"` public exposure.
- Avoid N+1 queries in query adapters using deliberate
  `select_related`/`prefetch_related`/projections.
- Unfold admin classes inherit from matching Unfold classes.
- Public API stays under `/api/v1/` unless versioning is explicitly changed;
  `make schema-check` stays warning-free.
- Schema changes require migrations; never rewrite an applied migration merely
  to make checks pass.

## Security rules
- Never hard-code secrets/credentials/tokens/private keys/production hosts.
- Never read/write `.env`, `.env.*`, or `secrets/**` unless explicitly asked.
- Production: `DEBUG=False`, explicit hosts, secure cookies, HTTPS-aware
  settings/security middleware.
- Uploads, archives, redirects, rich HTML, deserialization, subprocesses and
  outbound URLs are security-sensitive; prefer allowlists.
- Never string-build SQL, use unsafe pickle/YAML loading, or use `shell=True`
  with untrusted data.

## Canonical workflow
Use uv only; do not introduce a parallel dependency manager.

```bash
make format
make architecture-check  # Import Linter contracts
make check               # canonical normal completion gate
make security            # security-sensitive changes
make test-fast            # optional local parallel test run
make package-build
make docker-build
```

`make check` includes lock/environment integrity, Ruff, **Import Linter**,
mypy, Django checks, missing migrations, OpenAPI validation, pytest and
coverage. Run focused tests while iterating, then `make check`. If a command
cannot run, state exactly why; never claim success without executing it.

## Testing
- Bug fixes require a regression test when practical.
- Domain tests should normally be plain fast Python tests without Django DB.
- Application-service tests should prefer fake repositories/UoW/ports when that
  tests behavior more directly than framework integration.
- Django DB tests verify persistence mappings, repositories, transactions,
  migrations, locking/query behavior, and admin/framework integration.
- New behavior covers success, invalid input, permissions and important edges.
- Use Hypothesis selectively for validation, paths/trees, serialization,
  permissions and other invariant-heavy input spaces.
- Tests are deterministic/network-independent. >=85% project coverage is a
  backstop, not a substitute for meaningful changed-path tests.

## Dependency discipline and review priorities
- `uv.lock` is committed/authoritative after bootstrap; never hand-edit it.
- Review new dependencies for maintenance, license, security and footprint.
- Never weaken lint/type/architecture/test/security gates to make code pass.

Review in order: security/authorization; correctness/data integrity/concurrency;
persistence boundaries/transactions; registry/plugin/content/block schema compatibility; API contracts;
reliability/observability; query behavior/performance; typing/tests. Use the
repository review/quality/fix skills and specialist reviewers when useful.
