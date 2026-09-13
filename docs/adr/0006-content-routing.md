# ADR 0006: Content routing is an optional attached tree, not a content field

- Status: Accepted
- Date: 2026-09-13

## Context

Strata needs page hierarchy/routing (parent/slug tree, path resolution for the
Delivery API, move/rename) without making every content item carry tree
fields it doesn't need. `ContentCapability.ROUTABLE` already existed as a
declared enum value with no implementation behind it.

Per the existing architecture invariant, "Page hierarchy/routing is a page
concern, not the root content abstraction" — the `Content` aggregate itself
must stay generic.

## Decision

### Optional attached `ContentRoute`, not a Content field

Routing is a separate, optional record: `ContentRoute(content_id, parent_id,
slug, version)`, living in its own small domain module
(`domain/route.py`), attached via an explicit `attach_route` use case.
Content that never attaches a route carries no routing data at all — most
content types (this example repo's `article`) are never in the route tree.
This was chosen over a dedicated built-in `strata.page` content type because
it lets *any* content type become routable without coupling routing to one
specific schema shape.

`ContentRoute` only self-validates local invariants (slug shape, not
self-parented). Cross-node invariants — cycles, sibling slug uniqueness — need
the repository and are therefore enforced by the application use cases
(`attach_route`/`move_route`/`detach_route`), not the value object.

### Path is a rebuildable projection, synchronously rebuilt

Per "published routing may be an optimized projection" and "route/publication
state transitions must be transactionally/reliably consistent": the
authoritative data is only `(content_id, parent_id, slug)`. The full `path`
string (e.g. `about/team`) is *never* stored as authoritative data on a node;
it is recomputed into a separate `RoutePathRecord` projection
(`path -> content_id`, unique on `path`) by `move_route`/`attach_route`, which
walk the moved node's ancestor chain and then recursively rebuild every
descendant's path, inside the same database transaction as the route change.
This was chosen over an async/eventually-consistent rebuild (the pattern used
for search indexing) because there was no evidence this needs to scale past a
synchronous rebuild, and immediate consistency is simpler to reason about for
a tree operation a human editor is watching complete.

The path projection is purely structural. Resolving a path to delivery-ready
content still goes through the normal published-content read path
(`get_published_content`), so a routed-but-unpublished (or archived) item
resolves to nothing — routing can never leak drafts.

### Persistence

`ContentRouteRecord` (parent/slug, `OneToOneField` to `ContentRecord`) enforces
sibling-slug uniqueness with two partial unique constraints — one scoped to
`parent IS NOT NULL`, one to root-level (`parent IS NULL`) — since a plain
`unique_together` would let two root routes share a slug (SQL `NULL` is never
equal to `NULL`). `RoutePathRecord` is a separate table so the frequently-read
path projection is never joined against the write-frequency route table.

### Authorization

Route mutations reuse the existing `ContentAction.CHANGE` permission rather
than introducing new route-specific Django permissions; routing was not
identified as needing authority separate from general content editing.

## Consequences

Benefits:
- non-routable content (most content types) carries zero routing overhead;
- any content type can become routable without a special base class or schema;
- path resolution for the Delivery API is a single indexed lookup, not a tree
  walk;
- move/rename is immediately consistent — no stale-path window to reason
  about or test around.

Costs:
- moving a very large subtree does more work per request than an async
  rebuild would (synchronous, in-transaction);
- no site/multi-tree scoping yet — a single global tree;
- no scheduled publish/unpublish interaction with routing beyond what the
  existing publish/archive use cases already provide.

## Rejected alternatives

### Dedicated built-in `strata.page` content type

Rejected because it couples routing to one specific content shape
(title/slug/parent/body) rather than letting any content type opt in, and
duplicates what content types already do for their own schemas.

### Storing `path` as authoritative data on each node

Rejected because renaming/moving an ancestor would require rewriting every
descendant's authoritative row as part of correctness, not just as a
projection rebuild — indistinguishable in practice from the chosen design,
but framed incorrectly as source-of-truth data instead of a derived index.

### Async path rebuild via the outbox worker (mirroring search indexing)

Rejected for now: no evidence of a need to scale past a synchronous,
in-transaction rebuild, and immediate consistency avoids an eventually-stale
path window after a move. Revisit if move/rename operations on very large
subtrees become a real performance problem.
