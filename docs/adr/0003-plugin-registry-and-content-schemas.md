# ADR 0003: Compiled plugin registry and typed content schemas

- Status: Accepted
- Date: 2026-09-12

## Context

Strata must allow third-party code to add content types and later blocks,
admin/API integration, search definitions, hooks and infrastructure adapters.
Persisted content must remain readable across plugin upgrades, and startup must
fail deterministically for invalid plugin graphs rather than discovering
configuration errors during requests.

Django `AppConfig.ready()` is not a suitable mutable global-registration bus:
ordering is framework-driven, side effects are difficult to reason about, and a
registry can be frozen too early if request/runtime code touches it during app
loading.

## Decision

Strata uses a two-phase registry:

1. `StrataRegistryBuilder` is mutable only while the application is compiling its
   plugin configuration.
2. `StrataRegistry` is immutable and exposes lookup only. Successful `build()`
   consumes the builder; later mutation fails.

Plugins have stable namespaced `PluginKey`s and declarative `PluginDefinition`
metadata. Plugin dependencies use PEP 440 version constraints, are validated as
a complete graph, and are compiled in deterministic dependency-first order.
Duplicate keys, missing/incompatible dependencies, CMS-version incompatibility,
plugin-API incompatibility and dependency cycles fail registry compilation.

Django plugins may subclass `StrataPluginConfig`. They do not mutate a global
registry in `ready()`. The central Django registry loader gathers installed
`StrataPluginConfig` applications only after Django app loading has completed,
registers each plugin definition, and gives each callback a **scoped
`PluginRegistrar`** that can register definitions only for that plugin. It then
compiles one registry. Django system checks compile the registry so invalid
registrations fail CI and startup checks.

The supported third-party contract is `strata_cms.plugin_api`. Plugins must not
import Strata private infrastructure simply because it is convenient.

## Content schemas

Each `ContentTypeDefinition[T]` owns:

- a stable `ContentTypeKey`;
- a current positive persisted schema version;
- a typed `ContentSchema[T]` serializer/deserializer/validator;
- a complete pure migration chain from schema version 1 to current;
- optional Delivery API serialization and CMS capabilities.

Historical revision rows are immutable. Reading a historical revision migrates
its payload **in memory**, then decodes and validates the current typed value.
Plugin upgrades do not rewrite historical revisions automatically.

New content/revisions pass through the application `ContentTypeService` port.
The registry-backed adapter migrates/validates supported input and serializes it
back to the plugin's current canonical schema before persistence. Thus newly
created revisions use the current schema even when an import/client submitted a
supported historical representation.

Publishing validates that the chosen immutable revision can still be decoded by
the installed content type before changing the published pointer.

## Consequences

- Persisted type keys are independent from Python import paths and database IDs.
- Plugin graph failures are deterministic startup/check failures.
- Application/domain code remains independent from the concrete registry.
- Historical snapshots preserve exactly what was originally stored while still
  being readable after schema evolution.
- Schema migrations must be pure, adjacent and complete; database/provider work
  belongs in explicit application/infrastructure migrations instead.
- Disabled/uninstalled plugin content may remain stored safely, but normal
  decoding/editing/delivery is unavailable until a compatible plugin returns.
- Plugin API compatibility is a product compatibility concern separate from
  plugin package versions and persisted content schema versions.

## Rejected alternatives

- Runtime scanning/guessing of plugin classes: non-deterministic and difficult
  to validate/debug.
- Persisting Python import paths as type identity: breaks ordinary refactors.
- Mutating a global registry from `AppConfig.ready()`: side-effect ordering and
  freeze timing are fragile.
- Rewriting every historical revision when a plugin schema changes: destroys
  historical fidelity and makes plugin upgrades operationally dangerous.
- Runtime-defined Django model schemas: weakens typing, migrations, indexing,
  static analysis and extension compatibility.
