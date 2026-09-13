# Contributing

## Setup

```bash
cp .env.example .env
make bootstrap
uv run python manage.py migrate
```

After `uv.lock` has been committed, fresh clones should use:

```bash
make install
```

## Plugin and content-schema changes

Public plugin contracts live under `strata_cms.plugin_api`; third-party-facing
code must not rely on private infrastructure modules. Follow ADR 0003.

When changing a persisted content schema:

- increment its schema version deliberately;
- add every adjacent pure migration required to reach the new current version;
- add tests reading historical payloads and serializing current Delivery data;
- do not rewrite historical revisions as part of ordinary plugin startup;
- run `make architecture-check` and `make check`.

Django plugin applications should expose `StrataPluginConfig.register_strata()`
declarations using the provided owner-scoped `PluginRegistrar`. Do not perform
database/network/broker/cache work while compiling the registry, do not request
the raw builder from plugin code, and do not mutate a global registry from
`AppConfig.ready()`.

## Editor/Management changes

Schema-driven editing follows ADR 0005. Content/block schemas remain the
validation authority; editor metadata is a presentation hint layer. Keep Admin
and Management API writes on the shared content/revision use cases, preserve
optimistic concurrency, and do not add a persistence-record ModelForm write
path. Changes to editor metadata or Management endpoints require focused tests
and warning-free `make schema-check`.

## Workflow

Keep changes focused and add tests with behavior changes. Use migrations for model changes and document changes to public APIs or extension points.

During development use focused checks/tests. Before opening a PR:

```bash
make architecture-check
make check
make security
```

For packaging/runtime changes also run:

```bash
make package-build
make docker-build
```

API changes must keep `make schema-check` warning-free and should be reviewed for OpenAPI compatibility. Bug fixes should include regression tests where practical. Hypothesis is encouraged for input-heavy or invariant-heavy behavior where examples alone are weak.

See `docs/ai/standards.md`, `docs/ai/architecture.md`, `docs/ai/infrastructure.md`, `docs/ai/security.md`, and `docs/ai/tooling.md` for the rules shared by humans, Claude Code, Codex, and CI.
