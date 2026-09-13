# ADR 0005: Schema-driven management editor

- Status: Accepted
- Date: 2026-09-12

## Context

Strata needs one editing contract usable by Django Admin/Unfold and by
external Management API clients. The domain/content schema must remain the
validation authority, and immutable revisions must remain the persistence unit.
A second mutable draft model or Admin-specific Active Record write path would
violate ADRs 0001–0004.

## Decision

Plugins may optionally attach presentation-neutral editor metadata to content
and block definitions. Editor metadata describes human labels, semantic input
hints, field ordering, block collection presentation, slot labels, and initial
working-document data. It does not define domain validation or persistence.

The editor vocabulary is intentionally small. Built-in scalar hints include
text, textarea, slug, email, URL, integer, decimal, boolean, date/datetime,
choice, and multi-choice inputs. Management clients are free to render these
differently. Unsupported advanced UI needs a deliberate future extension
contract rather than arbitrary HTML/JavaScript embedded in plugin metadata.

Hints such as `required` and `read_only` are presentation/interaction hints
only. They are not authorization controls and do not replace server-side schema
validation or application policy.

Structured block semantics remain owned by `BlockFieldDefinition`, block slot
definitions, and registered block schemas. Editor metadata only adds labels and
input hints. A client creates a block envelope from the registered current
schema version and initial data, allocates a UUID, and manipulates ordering and
nesting in its ephemeral working document. Saving sends the complete working
document through the existing content/revision use case, which recursively
normalizes and validates it before an immutable revision is appended.

The Management API exposes:

- installed content editor summaries;
- one compiled content editor contract, including all reachable block types;
- latest working content/revision state;
- create-content, create-revision, and publish operations.

Writes retain optimistic aggregate version checks. The default Management API
requires staff status plus explicit Django view/add/change permissions until
finer-grained policy/object authorization is implemented.

Django Admin/Unfold is a management client. `ContentRecord` may be registered
for framework discovery/listing, but Django's model change form is not a CMS
write path. Add/change views render the generic editor and persist through the
Management API/application use cases. Deletion remains disabled until an
explicit delete/archive use case exists.

## Consequences

- Content/block schemas and editor metadata can evolve independently.
- Invalid editor working state can exist in the browser, but only valid schema
  state can become a persisted revision.
- Drag/drop/reorder/nesting need no mutable server-side draft rows.
- Admin and external editors consume the same contract and concurrency rules.
- Plugins without editor metadata remain valid for programmatic/imported
  content but are reported as non-editable by generic management clients.
- The editor contract is not intended to become a full frontend framework.
