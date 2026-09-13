# ADR 0004: Structured blocks are revision-embedded typed trees

- Status: Accepted
- Date: 2026-09-12

## Context

Strata needs flexible editorial composition without runtime-created Django
models, mutable Active Record block rows, or a different tree encoding for every
plugin. Blocks also need to survive plugin upgrades and historical revision reads
without rewriting immutable history.

## Decision

A block is an immutable value embedded inside a content revision. Its stable
envelope is owned by Strata and contains:

```json
{
  "id": "uuid",
  "type": "vendor.block_type",
  "version": 2,
  "data": {},
  "slots": {
    "children": []
  }
}
```

`id` is a stable UUID retained when the same logical block is edited into a new
content revision. `type` is a durable namespaced `BlockTypeKey`, not an import
path. `version` is the block data schema version and evolves independently from
the surrounding content schema version. `data` belongs to the plugin's typed
`BlockSchema[T]`. `slots` belong to the CMS tree model.

Container blocks declare named `BlockSlotDefinition`s. Each slot declares
cardinality and optionally an allowlist of block types. Content types expose
block-bearing revision fields through `BlockFieldDefinition`; those fields have
the same collection constraints at their root.

The registry contains a frozen `BlockTypeRegistry`. During registry compilation,
all explicitly referenced block types must exist. If plugin A explicitly allows
a block owned by plugin B, A must declare B (directly or transitively) as a
plugin dependency.

Historical block schemas migrate in memory through complete adjacent pure
migration chains. New revision writes recursively normalize every declared
block to its current schema while preserving block UUIDs. Historical revisions
are never mass-rewritten merely because a plugin is upgraded.

Delivery serialization recursively emits the stable block identity/type/tree
shape but uses each block definition's current Delivery serializer for `data`.
Persisted schema version is an internal compatibility concern and is not required
in the public Delivery representation.

Block parsing and normalization enforce a finite nesting depth to avoid
pathological or malicious recursive payloads.

## Consequences

Benefits:
- no mutable block persistence model separate from immutable revisions;
- block schema upgrades are independent from content schema upgrades;
- stable identities enable future diffing/comments/editor operations;
- named slots support sections, columns, lists, and other containers without
  plugin-specific tree encodings;
- generic validation and Delivery traversal work across third-party blocks;
- historical content remains byte-for-byte preserved in storage.

Costs:
- editing a block creates a new content revision rather than updating a row;
- plugin authors must maintain block migration chains;
- relational querying inside arbitrary block trees is intentionally not the
  authoritative query model; search/routing/reporting should use projections;
- operations needing semantic references inside block data require explicit
  indexing/projection support rather than ORM joins against block rows.

## Rejected alternatives

### One Django model/table per block

Rejected because it reintroduces Active Record persistence, mutable state,
revision-copy complexity, and plugin migration coupling.

### Generic block rows plus parent/child foreign keys

Rejected as the authoritative editorial model because immutable revision
snapshots would then depend on mutable external rows and require complicated
version joins.

### Children embedded arbitrarily inside each plugin's `data`

Rejected because Strata core could not generically validate, migrate, traverse,
diff, or render nested block trees.

### One universal `children` list

Rejected because named slots express real container semantics such as
`left`/`right`, `header`/`body`, or `items` without smuggling structure into
block-specific data.
