# Strata architecture contract

This document is normative for implementation and review. Do not silently
replace these decisions with another CMS architecture because a framework
shortcut is more familiar. Database/cache/search/messaging/task/storage details
are additionally normative in `docs/ai/infrastructure.md`.

## Architectural goal

Build a **headless-first modular monolith with a stable plugin contract**.

The CMS is generic because code extends it through explicit, typed extension
points. It is not generic because administrators create arbitrary database
models/fields at runtime.

Prefer code-defined domain/content types, explicit persistence records and
migrations, typed plugin registrations, and flexible versioned structured
blocks. Do not introduce microservices, runtime-defined model schemas, a
bespoke admin SPA, GraphQL, a workflow engine, or mandatory Redis/Celery/
OpenSearch/etc. without a concrete requirement.

## Package and dependency direction

The architectural seams begin as:

```text
strata/
├── domain/            # plain Python entities, value objects, domain rules
├── application/       # use cases, commands/queries, ports, UoW contracts
├── infrastructure/    # Django ORM/provider adapters and mappings
├── api/               # DRF presentation adapter
├── admin/             # Django Admin/Unfold presentation adapter
└── config/            # composition root / Django configuration
```

As features grow, keep them cohesive within these seams rather than creating a
single giant `models.py` or `services.py` dumping ground.

Dependency rules:
- domain depends on neither application, infrastructure nor Django/DRF;
- application depends on domain and application-owned ports only;
- infrastructure implements those ports and may depend on provider/framework
  code;
- API/admin/CLI/worker call application use cases rather than persistence
  records directly;
- configuration/bootstrap is the composition root and may wire adapters;
- third-party plugins depend only on documented public CMS contracts;
- do not import another feature/plugin's private internals.

Import Linter contracts in `pyproject.toml` enforce stable import-level parts of
this architecture. Do not weaken/ignore those contracts to work around an
invalid dependency.

## Persistence is Data Mapper style

Django ORM is infrastructure, not the domain model. See
`docs/ai/infrastructure.md` for the complete contract.

Core rules:
- domain entities are plain Python and persistence-ignorant;
- Django ORM classes are persistence records, preferably named `*Record`;
- record↔entity mapping is explicit;
- repository interfaces return entities, not records/QuerySets;
- application use cases own transaction intent through Unit of Work ports;
- concrete Django repositories/query services/UoW live in infrastructure;
- read-only query services may return immutable DTOs/projections without
  hydrating aggregates when that is clearer/faster;
- custom Admin/API/CLI business operations all call the same use cases.

A domain entity may expose meaningful behavior such as `page.rename(...)`; it
must not expose persistence behavior such as `page.save()`.

## Content identity

Every independently manageable CMS object has a stable CMS identity.

Use:
- UUIDs for stable public/persistent identities;
- namespaced type keys such as `strata.page` or `acme_blog.article`;
- explicit relations where the relationship is known.

Do not use Django `ContentType` integer IDs as external/durable identities.
Avoid `GenericForeignKey` as the foundational content/plugin relationship
mechanism; a narrow exceptional use requires explicit architectural review.

A `Page` is one kind of content with routing/tree behavior. Not all content is
a Page. Do not force articles/products/authors/events/plugin models to inherit
page semantics merely to participate in the CMS.

## Revisions and publication

Publication is revision-based. The concrete core model is defined by
`docs/adr/0002-content-revision-aggregate.md`. Do not replace it with mutable
content rows or an `is_published` shortcut without reopening that ADR.

The built-in core uses a stable `Content` aggregate plus immutable `Revision`
snapshots. Content aggregate states are immutable too: lifecycle methods return
new state rather than allowing direct pointer/version assignment.
`Content.latest_revision_id` identifies current draft state;
`Content.published_revision_id` independently identifies delivery state. Creating
a revision must never implicitly republish content.

Invariants:
- revisions are immutable snapshots;
- persisted snapshots include schema/type version information required for
  safe deserialization/migration;
- draft/editable state and published state are distinct;
- Delivery API reads only the explicitly published revision;
- restoring history creates new working state/revision rather than mutating
  historical snapshots;
- publish/unpublish/restore are explicit application use cases;
- publication's authoritative writes occur atomically through Unit of Work.

Published routes/search/cache/read models may denormalize for efficient reads.
They are projections and must be derivable/rebuildable from authoritative
content/revisions. Do not make a JSON revision blob the only query structure
for indexed relational read paths.

## Structured blocks

Structured blocks are implemented as immutable values embedded in revision JSON;
they are not Django models or independently mutable records. ADR
`0004-structured-blocks.md` is normative.

Every persisted block envelope contains:
- stable UUID retained across revisions when the editor is modifying the same
  logical block;
- stable namespaced block type key;
- independent block schema version;
- structured JSON `data`;
- named nested `slots`, each containing an ordered block collection.

The CMS owns the envelope/tree format. A plugin `BlockSchema[T]` owns only the
typed `data` portion. Container/layout semantics use named slots such as
`children`, `left`, `right`, or `items`; do not invent plugin-specific child-tree
formats inside block data.

Block definitions declare slot cardinality and allowed child block types. Content
types declare block-bearing JSON fields with `BlockFieldDefinition`. Registry
compilation validates referenced block keys, and explicit references to blocks
owned by another plugin require a declared plugin dependency.

Read/write rules:
- historical block data migrates in memory through complete adjacent pure
  migrations, independently from the surrounding content schema version;
- new revision writes normalize every declared block recursively to the current
  canonical block schema while preserving block UUIDs;
- block validation includes envelope shape, nesting depth, collection
  cardinality, allowed block types, known slot names, typed block data, and
  semantic validation;
- Delivery serialization uses block-specific serializers recursively and does
  not expose persisted block schema versions as a public API requirement;
- missing block plugins/types make normal decode/edit/publish/delivery invalid
  but do not corrupt or delete historical revision JSON.

Block nesting is bounded defensively. Keep migrations deterministic and free of
DB/network/time/random I/O; if a migration needs an identifier, derive it
deterministically from existing persisted data/context rather than generating a
random value during reads.

Prefer structured rich text. Raw HTML is not the default storage/interchange
format and any raw-HTML capability is security-sensitive, explicit and
controlled.

## Application/use-case layer

Business operations live in explicit application use cases/services, e.g.:
- create/update content;
- create revision;
- publish/unpublish/restore;
- move/rename page;
- schedule publication;
- media lifecycle operations;
- retry/replay operator actions for durable jobs/messages.

Django Admin, Management API, management commands and workers call these same
use cases.

Do not hide workflow in:
- Django model `save()`/`delete()` overrides;
- `ModelAdmin.save_model()` or actions beyond adapter glue;
- DRF view methods beyond transport concerns;
- Django signals.

Signals/events may announce completed facts; they are not the implementation of
the publish/edit transaction.

## Plugin system

ADR `0003-plugin-registry-and-content-schemas.md` is normative. Plugins are
normal Python/Django applications with explicit registration through the public
`strata_cms.plugin_api` contract.

Registry lifecycle:
- `StrataRegistryBuilder` is mutable only during startup compilation;
- plugins register declarative metadata/definitions, not runtime work;
- dependency/version/API compatibility is validated and topologically ordered;
- successful compilation consumes the builder and returns immutable
  `StrataRegistry`;
- runtime code performs lookup only; it never registers/mutates definitions;
- the Django adapter gathers installed `StrataPluginConfig` applications after app
  loading instead of using `AppConfig.ready()` as a global mutation bus; each
  plugin callback receives an owner-scoped `PluginRegistrar`, not the builder;
- Django system checks compile the plugin graph so invalid registration fails
  CI/startup checks.

Required properties:
- explicit, typed, deterministic, namespaced registration;
- no arbitrary package scanning/class guessing;
- duplicate keys, missing/incompatible dependencies, incompatible CMS/plugin
  API versions and dependency cycles fail clearly;
- persisted identifiers do not depend on import paths or database-local IDs;
- third-party plugins import documented `strata_cms.plugin_api` contracts, not
  private infrastructure modules.

Expected extension categories include content types, blocks, admin/API
integration, validation, policies, publish/event hooks, infrastructure adapter
registrations, search indexing and media processors. Add these as deliberate
typed subregistries/contracts rather than turning the registry into a generic
service locator.

Registration must be declarative and side-effect-free: do not query databases,
perform HTTP calls, connect brokers, write caches, schedule jobs or otherwise do
runtime application work while describing a plugin.

## Content type schemas and compatibility

A registered `ContentTypeDefinition[T]` owns a stable namespaced key, current
schema version, typed serializer/deserializer/validator, complete pure migration
chain, capabilities and optional Delivery API serializer. The schema represents
the immutable revision payload; it is not a Django model.

Rules:
- schema versions begin at 1 and advance deliberately;
- every transition to the current version has an adjacent pure migration
  (`1→2→3`, not gaps or arbitrary jumps);
- migrations transform `RevisionData` in memory and perform no DB/network/I/O;
- reading old revisions migrates in memory, then decodes and validates typed
  content; never rewrite all historical revisions merely because a plugin was
  upgraded;
- new content/revision writes go through the application `ContentTypeService`
  port and are re-encoded to the current canonical schema before persistence;
- publishing requires the chosen revision to remain decodable/valid with the
  installed plugin;
- Delivery serialization consumes typed current content, not raw historical
  payload dictionaries;
- an unavailable plugin does not invalidate stored rows: raw history may remain
  inspectable/exportable, but normal edit/publish/delivery is unavailable until
  a compatible plugin is installed.

Plugin package versions, plugin API versions and persisted content schema
versions are separate compatibility axes. Do not conflate them.


## Management editor metadata

ADR `0005-schema-driven-management-editor.md` is normative. Content/block
schemas remain the validation and persistence authority; optional editor
metadata only describes how humans can edit those schemas.

Rules:
- do not encode domain validation solely in editor metadata or JavaScript;
- treat `required`, `read_only`, choices, placeholders, and similar editor
  metadata as UX hints only; never use them as authorization or the sole
  validation mechanism;
- keep the editor vocabulary semantic and presentation-neutral rather than
  turning `plugin_api` into an HTML/widget framework;
- scalar editor paths and block editor paths identify JSON fields in the
  current content/block data representation; block constraints continue to
  come from `BlockFieldDefinition` and `BlockSlotDefinition`;
- plugins without editor metadata remain valid but are not generically editable;
- generic clients discover only blocks reachable from the selected content
  type's declared block fields/slots;
- new block UUIDs belong to the ephemeral working document and become durable
  only when a validated revision is persisted;
- reordering/nesting mutates only the browser/client working document. Do not
  introduce mutable `BlockRecord` or server-side row-per-edit draft state;
- saving an editor document always calls the same create-revision/content use
  cases and retains optimistic aggregate version checks;
- Django Admin/Unfold is a Management client. It may register persistence
  records for framework listing/discovery, but generic CMS writes must not use
  `ModelForm.save()`/`ModelAdmin.save_model()` as a second workflow;
- Management API and Admin must translate validation/concurrency failures into
  explicit user-facing errors without weakening server-side validation;
- generic deletion/archive/publish/etc. require explicit use cases; do not use
  Django record deletion merely because the Admin framework exposes it.

The initial generic editor supports a deliberately small semantic input
vocabulary. Add richer/custom widgets only through an explicit versioned
extension contract when a real use case appears.


## APIs

Keep Delivery and Management APIs conceptually separate even when both use DRF.

### Delivery API
- read-only by default;
- published content only;
- cache/CDN friendly;
- explicitly versioned under `/api/v1/`;
- may derive ETag/cache validators from published revision identity;
- never exposes draft/private fields via serializer convenience.

### Management API
- authenticated and explicitly/object-level authorized;
- calls the same application use cases as Admin;
- may expose drafts/revisions/publish/workflow/preview;
- uses optimistic concurrency (base revision/version token/`If-Match` style)
  to prevent silent lost updates.

API changes require tests and warning-free OpenAPI generation; inspect
externally observable schema diffs.

## Preview

Preview targets a specific non-published revision and requires scoped,
expiring authorization. Knowing a revision UUID must never make a draft
publicly retrievable.

## Permissions and workflow

Build on Django auth/permissions where useful but keep authorization decisions
behind explicit policy/use-case boundaries.

Separate edit and publication authority. Possible actions include
view/add/change/delete/publish/unpublish/restore, with site/subtree/object scope
possible later.

Start workflow simple: draft + published/unpublished, plus scheduled
publish/unpublish when implemented. Do not pre-build a general BPM engine.

## Pages and routing

Page hierarchy/routing is a page concern, not the root content abstraction.

- page moves/renames go through use cases preserving tree/path invariants;
- use proven tree/path techniques/libraries rather than casual custom trees;
- published routing may be an optimized projection;
- route/publication state transitions must be transactionally/reliably
  consistent.

## Media

Media is a first-class CMS entity, not arbitrary `FileField`s scattered through
plugins. Stable media identity is independent from its storage key/provider.

Track appropriate metadata such as filename, storage key, MIME type, size,
checksum, dimensions, ownership/audit and derived metadata.

Use Django Storage as the baseline adapter where suitable; local/object storage
providers stay replaceable. Derived rendition processing remains optional and
uses the task/message abstractions described in `docs/ai/infrastructure.md`.

Uploads/media processing are security-sensitive.

## Infrastructure capabilities and async work

Infrastructure contracts are defined in `docs/ai/infrastructure.md`.

Baseline principles:
- narrow ports for cache/search/events/tasks/messages/storage/clock;
- PostgreSQL + normal storage is the intended minimal production dependency;
- optional external providers implement ports rather than leaking SDKs into
  application/domain code;
- events, tasks and broker transport are distinct abstractions;
- durable processing is at-least-once/idempotent;
- reliable integration events use a transactional outbox;
- intended simple async default is an optional PostgreSQL-backed worker using
  the same application image;
- search/cache/route indexes are disposable/rebuildable projections.

Do not make Redis/Celery/RabbitMQ/Kafka/OpenSearch mandatory simply because an
implementation is easier with them.

## Localization and multi-site readiness

Do not model localization as fields like `title_en`, `title_cs`, etc. Keep
identity/revision architecture capable of first-class locale/site variants if
those features are later required, without prematurely implementing them.

## Review checklist

Architecture reviewers must ask:
- Did Django ORM/Active Record persistence leak outside infrastructure?
- Do application services own transaction/use-case semantics once?
- Does this preserve draft vs published isolation?
- Can historical revisions/messages/blocks still be read after schema/plugin
  evolution?
- Is dependency direction valid and executable contracts still intact?
- Are extension points explicit, namespaced, typed and deterministic?
- Are permissions checked at the right use-case/object boundary?
- Are multi-write transitions atomic and concurrency-safe?
- Are projections/search/cache rebuildable from authoritative state?
- Are durable messages at-least-once and handlers idempotent?
- Was mandatory external infrastructure introduced without a requirement?
- Is a new abstraction solving a current problem rather than hypothetical
  provider/plugin needs?
