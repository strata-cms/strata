# ADR 0002: Content identity and immutable revision aggregate

- Status: Accepted
- Date: 2026-09-12

## Context

Strata needs stable content identity, editable draft state, explicit
publication, history, preview, optimistic concurrency, and plugin-owned payload
schemas without allowing mutable Django ORM rows to become the public/domain
model.

A conventional Active Record model with editable fields and an `is_published`
flag risks draft leakage and makes historical state difficult to preserve.
Keeping separate mutable draft and published copies also creates synchronization
and duplication problems.

## Decision

Use a stable `Content` aggregate identity plus append-only immutable `Revision`
snapshots.

Domain `Content` instances are immutable state values: domain operations return a
new aggregate state rather than exposing assignable lifecycle fields. Identity remains
stable across those states.

`Content` stores only lifecycle identity/pointers and concurrency metadata:

- stable UUID and namespaced content type key;
- creation audit metadata;
- latest revision identity/number;
- optional published revision identity and publication audit metadata;
- monotonically increasing aggregate version.

Every edit creates a new immutable `Revision` containing:

- stable UUID;
- owning content UUID;
- monotonically increasing per-content revision number;
- content type key;
- persisted payload schema version;
- strict JSON snapshot data;
- creation audit metadata.

The public/delivery state is the explicitly published revision. Creating a new
revision changes the latest/draft pointer only and never implicitly republishes
content. Publishing is an application use case that atomically changes the
published pointer and inserts a versioned `strata.content.published`
integration event into the transactional outbox.

Django records are persistence-only representations. Repositories and explicit
mappers translate them to/from domain objects. Revision records are append-only
through the repository API.

## Concurrency

Management mutations carry an expected aggregate version. A stale version is a
conflict, not last-write-wins behavior.

The Django write Unit of Work also loads content records with `SELECT ... FOR
UPDATE` where supported. This serializes revision-number allocation inside the
database while the aggregate version remains the externally meaningful
optimistic-concurrency token.

Repository updates use compare-and-swap (`WHERE id = ? AND version = ?`) as a
second integrity guard.

## Persistence integrity

The database enforces:

- foreign keys from revisions to content and content revision pointers to
  revision rows;
- uniqueness of `(content_id, revision_number)`;
- consistency between latest revision pointer and latest revision number;
- consistency between published revision pointer/time/actor fields.

The domain/application layer additionally enforces that a published revision
belongs to the target content item and has the same content type. Cross-row
"published revision belongs to this same content" is not representable as a
simple portable SQL check constraint and remains a domain invariant.

## Consequences

Benefits:

- drafts cannot leak merely because a mutable row was saved;
- history and preview have stable immutable identities;
- publishing or rolling back to an older revision is a pointer operation;
- content payload schemas can evolve independently through explicit schema
  versions;
- delivery caching/ETags can key off published revision identity;
- reliable downstream reactions can consume the transactional outbox.

Costs:

- payloads are snapshots and may duplicate data between revisions;
- plugin schema evolution requires explicit read/migration compatibility;
- query-heavy published fields may need rebuildable projections rather than
  querying JSON snapshots directly;
- Admin editing must eventually translate forms into application commands
  rather than treating persistence records as the editorial domain model.

## Rejected alternatives

### Mutable Active Record content models

Rejected because persistence behavior and draft/public lifecycle become coupled
and too easy to bypass from Admin, API code, scripts, or agents.

### Event sourcing as the authoritative model

Rejected for now. Immutable revisions plus explicit integration events provide
the required CMS history without imposing event-sourced reconstruction on all
state.

### Separate mutable draft and published tables

Rejected because synchronization, identity, and rollback semantics become more
complex than explicit immutable revisions and publication pointers.
