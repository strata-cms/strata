# Infrastructure and persistence contract

This document is normative for database, cache, search, messaging, task,
storage, clock/time, and other infrastructure work.

## Core principle

Infrastructure is accessed through narrow CMS-defined ports. Domain entities
and application use cases must not depend on Django ORM, Redis, Celery,
RabbitMQ, Kafka, OpenSearch, S3, or any other concrete provider.

The default installation should remain useful with Django + PostgreSQL + normal
storage wherever practical. External systems are adapters, not assumptions.

## Persistence model: Data Mapper over Django ORM

This decision is recorded in `docs/adr/0001-data-mapper-over-django-orm.md`.
Do not add SQLAlchemy or a second ORM without explicitly reopening that ADR.

Django ORM is allowed because Django admin, migrations, auth, relations, and
framework integrations benefit from it. Its Active Record API is an
**infrastructure implementation detail**, not the application/domain model.

### Domain entities

Domain entities are plain Python objects (typically dataclasses or focused
classes) with identity and domain behavior. They may mutate their in-memory
state through meaningful domain operations, but they must not know how they are
stored.

Allowed example:

```python
page.rename("New title")
```

Architecturally forbidden outside the Django persistence adapter:

```python
page.save()
PageRecord.objects.filter(...)
record.delete()
transaction.atomic()
```

The domain package must not import Django, DRF, ORM models, QuerySet, database
connections, or infrastructure adapters.

### Persistence records

Django `models.Model` classes are persistence records. Prefer explicit `Record`
suffixes such as `PageRecord`, `RevisionRecord`, and `OutboxMessageRecord` so
persistence objects are visually distinguishable from domain entities.

Records live under `strata_cms.infrastructure.persistence.django` (or a
feature-local infrastructure persistence adapter when the repository evolves
to bounded-context-local adapters). ORM queries, `.save()`, `.delete()`, model
managers, `select_for_update()`, raw SQL, and `transaction.atomic()` belong only
inside persistence/query adapters and framework-owned admin mechanics.

Do not put business invariants or cross-record workflows in model `save()` or
`delete()` overrides.

### Mappers

Mapping between records and entities is explicit. Do not pass persistence
records through application services merely to avoid writing a mapper.

Mapping code must account for:
- value-object construction/validation;
- enum/version conversion;
- optional relationships;
- schema evolution/backward compatibility;
- avoiding accidental lazy-load I/O from domain code.

### Repositories

Repository interfaces belong to the domain/application-facing side of the
boundary and return domain entities, not records or QuerySets.

Repository implementations live in infrastructure and use the Django ORM.
Repositories should model aggregate persistence needs rather than exposing a
generic CRUD ORM replacement.

Avoid repository methods that leak storage syntax, such as accepting `Q`
objects, ORM lookup strings, or returning QuerySets.

### Unit of Work

Application use cases own transaction intent through a Unit of Work port.
The built-in content write UoW loads aggregate rows with `select_for_update()`
where supported so per-content revision numbers are allocated serially. This
pessimistic database lock complements rather than replaces the externally
meaningful optimistic aggregate version / compare-and-swap check.

Concrete Django units of work implement it with `transaction.atomic()` and
provide the repositories required by the use case/bounded context.

Multi-write state changes such as publication, revision creation, route
projection updates, and transactional outbox insertion must commit or roll back
as one unit.

Do not open hidden nested transactions in arbitrary repositories unless the
semantics are explicitly documented and tested.

### Query/read side

Do not force read-only API/admin/reporting queries through hydrated domain
entities when doing so creates unnecessary mapping or N+1 behavior.

Use query-service interfaces that return immutable DTOs/read models. Their
infrastructure implementations may use optimized Django ORM queries, database
views, PostgreSQL-specific search/query features, or rebuildable projections.

This is pragmatic command/query separation, not a requirement to build a full
CQRS/event-sourcing system.

### Django Admin

Django Admin/Unfold may register Django persistence records because that is a
framework requirement. Framework-driven form persistence is tolerated at this
presentation/infrastructure seam.

However, custom admin actions and any operation with business meaning
(publish, unpublish, restore, move, approve, retry, etc.) must invoke the same
application service/use case used by the Management API or CLI. Do not
implement a second workflow in `ModelAdmin.save_model()`, actions, or forms.

## Dependency direction

The intended dependency direction is:

```text
api/admin/cli/worker
        |
        v
application  ---> domain
        ^          ^
        |          |
infrastructure adapters
```

More precisely:
- `domain` imports neither application nor infrastructure/framework packages;
- `application` may import domain and application-owned ports, but not concrete
  infrastructure or Django/DRF;
- infrastructure implements domain/application-facing ports and may import
  Django/provider SDKs;
- API/admin/CLI call application use cases; API must not directly use Django
  persistence records;
- configuration/bootstrap is the composition root and may wire concrete
  adapters to ports.

Import Linter contracts in `pyproject.toml` enforce the parts of this boundary
that are expressible as imports.

## Capability ports

Use separate semantic ports instead of a single universal provider abstraction.
Expected core capabilities include:

- `Clock`;
- `Cache` / semantic cache services;
- `SearchBackend`;
- `EventPublisher`;
- `TaskQueue`;
- low-level durable `MessageQueue` only where transport semantics are needed;
- object/media storage, normally adapted from Django's Storage API;
- repositories/query services/Unit of Work for persistence.

Do not create a provider abstraction unless application/domain code has a real
need for it.

## Clock

Time-dependent application logic receives a `Clock` port rather than calling
`datetime.now()`/`timezone.now()` throughout domain/application code.

Default: system/Django-aware clock.
Tests: frozen/deterministic clock.

Use this for scheduled publishing, retries, embargoes, expirations, cache TTLs,
and other time-based behavior.

## Cache

Keep the cache port narrow. Prefer semantic services such as
`PublishedContentCache` over exposing raw Redis primitives to application code.

Default: Django cache adapter (LocMem in lightweight development; a configured
shared backend in deployments that need one).

External implementations may use Redis or another provider. Domain/application
code must not depend on Redis commands, keyspace notifications, Lua scripts,
or provider-specific serialization.

Cache entries are disposable projections. Correctness must never depend on a
cache entry surviving.

## Search

Search uses CMS-owned request/result/document DTOs rather than leaking a
provider query DSL through application code.

Baseline backend: PostgreSQL search capabilities when content/search models are
implemented.
Optional adapters: OpenSearch, Elasticsearch, Meilisearch, Typesense, or other
providers.

A backend may expose explicit capability flags (facets, fuzzy search,
highlighting, geo search, suggestions, etc.). Do not distort the baseline API
to emulate every advanced provider feature.

Search indexes are rebuildable projections of authoritative published content.
Drafts are excluded unless an explicitly authorized editor/preview search says
otherwise.

## Events, messages, and tasks

Do not collapse these concepts into one vague `Queue` abstraction.

### Event

An event states that something happened, e.g. `content.published`. The producer
must not know which integrations consume it.

### Task

A task requests work, e.g. `generate_image_renditions` or `deliver_webhook`.
Task execution semantics may be implemented by the built-in worker, Celery, or
another task framework.

### Broker / durable message queue

A broker/queue transports envelopes. RabbitMQ, PostgreSQL-backed queueing,
Kafka, SQS, etc. solve transport/delivery concerns. Celery is a task framework
that may itself use RabbitMQ/Redis/etc. as a broker; do not treat Celery and
RabbitMQ as equivalent adapters.

### Delivery semantics

The baseline contract is **at-least-once delivery**. Handlers must therefore be
idempotent or use idempotency keys/deduplication where side effects require it.
Do not claim exactly-once behavior across database and external services.

Message envelopes use stable UUIDs, namespaced/versioned message types, explicit
schema versions where payloads persist, timestamps, and correlation/causation
identifiers where useful.

### Transactional outbox

Reliable publication of integration events must use a transactional outbox
when the event must not be lost after an authoritative database commit.
Authoritative state and the outbox record are written in the same Unit of Work.
A worker then delivers/processes the message after commit.

Do not publish directly to RabbitMQ/Kafka/etc. inside a PostgreSQL transaction
and assume the operations are atomic.

### Built-in queue/worker

The intended simple production default is a PostgreSQL-backed durable queue and
an optional worker process using the same application image, for example:

```text
web     -> Django/Gunicorn
worker  -> python manage.py strata_worker
both    -> PostgreSQL
```

The worker is opt-in; the web/API process must still start without it. The
built-in queue should support safe multi-worker claiming, retry with backoff,
visibility/lease recovery after worker crashes, failure/dead-letter state, and
observability sufficient for operators.

PostgreSQL implementations should use appropriate row locking such as
`SELECT ... FOR UPDATE SKIP LOCKED` where supported. SQLite may provide reduced
single-process semantics for tests/local development; production queue
semantics are defined against PostgreSQL.

### External adapters

External packages should be able to implement the same public ports without
changing domain/application use cases, for example:
- Celery adapter implementing `TaskQueue`;
- RabbitMQ adapter implementing message transport/consumer ports;
- Kafka/SQS adapters where their semantics fit;
- an external event dispatcher fed by the transactional outbox.

Provider-specific options stay in the adapter/configuration layer.

## Storage

Use Django's Storage API as the baseline storage adapter where it already
provides the required abstraction. Wrap it only when the CMS needs a narrower
semantic port.

Default: filesystem storage for lightweight/local installations.
Optional: S3-compatible storage, Azure Blob, GCS, MinIO, etc.

Storage keys are not domain identities. Media entities retain stable UUID
identity independently of where bytes are stored.

## Configuration and system checks

Infrastructure adapters are selected explicitly through typed CMS settings or
an equivalent composition mechanism. Avoid hidden import-time provider
detection.

Django system checks should validate configured adapter importability,
interface compatibility, required settings, unsafe production defaults, and
incompatible capability combinations.

Third-party adapters should be installable as normal packages without modifying
Strata core.

## Review checklist

For infrastructure/persistence changes, reviewers must ask:
- Did Django ORM/QuerySet/record objects leak into domain/application/API?
- Is the entity/record mapping explicit and tested?
- Is transaction ownership at the use-case/Unit-of-Work boundary?
- Does a query service return a stable DTO instead of leaking QuerySet/provider
  syntax?
- Does the adapter expose only semantics the application needs?
- Is correctness independent of cache/search projections?
- Are events and tasks modeled distinctly?
- Are durable messages at-least-once and handlers idempotent?
- Can a DB commit occur without the required event/outbox record?
- Does an external provider create a mandatory dependency for the default
  installation?
- Can operators inspect/retry failed built-in messages when that feature is
  implemented?
