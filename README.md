# Strata

Strata is an extensible API-first CMS built on Django 5.2 LTS, Django REST Framework, and django-unfold. The Python distribution is `strata-cms` and the public Python namespace is `strata_cms`. It is designed for human development plus Claude Code and OpenAI Codex, with executable quality/security gates rather than prompt-only conventions.

## Baseline

- Python 3.12–3.14 supported; Python 3.14 is the default runtime and Docker base.
- Django 5.2 LTS.
- Django REST Framework 3.18.
- django-unfold admin.
- drf-spectacular OpenAPI schema/docs.
- PostgreSQL 18 for local containerized development/production-style use.
- uv for dependency management, lockfiles, environments, and package builds.
- Ruff for formatting, imports, linting, modernization, Django rules, and source security checks.
- mypy + Django/DRF stubs for typing.
- pytest, pytest-django, pytest-cov; Hypothesis and pytest-xdist available where useful.
- Import Linter for executable Data Mapper/dependency boundaries.
- pip-audit, CodeQL, Dependency Review, and Trivy for complementary security/supply-chain checks.

## Quick start

Install uv, then from the repository root:

```bash
cp .env.example .env
make bootstrap
uv run python manage.py migrate
uv run python manage.py createsuperuser
make run
```

`make bootstrap` creates `uv.lock`, synchronizes the environment, and installs pre-commit hooks. Commit the generated `uv.lock` immediately; after that use `make install` on fresh clones and CI uses locked installs only.

Open:
- Admin: `http://127.0.0.1:8000/admin/`
- API health: `http://127.0.0.1:8000/api/v1/health/`
- OpenAPI schema: `http://127.0.0.1:8000/api/schema/`
- Swagger UI: `http://127.0.0.1:8000/api/docs/`

For PostgreSQL + Docker:

```bash
docker compose up --build
```

## Canonical commands

```bash
make format        # Ruff autofix + formatter
make architecture-check # enforce domain/application/persistence imports
make check         # canonical completion gate
make security      # source/dependency/Django production security checks
make test          # canonical pytest + coverage
make test-fast     # optional pytest-xdist parallel run
make schema        # write validated openapi.yaml locally
make schema-check  # validate OpenAPI in a temporary file, fail on warnings
make package-build # build wheel + sdist with uv_build
make docker-build  # build production container
```

`make check` verifies the uv lock/environment, Ruff formatting/lint, Import Linter architecture contracts, mypy, Django system checks, missing migrations, warning-free OpenAPI generation, pytest, branch coverage, and the 85% project floor.

## Why this toolchain

Ruff replaces the overlapping Black/isort/Pylint/Bandit-style local stack with one fast formatter/linter. Import Linter separately owns architectural dependency constraints because those are not style rules. mypy remains separate because it performs semantic type analysis, especially with Django/DRF stubs. pip-audit remains the stable dependency vulnerability scanner; CodeQL adds deeper interprocedural security analysis in GitHub; Dependency Review blocks vulnerable dependencies introduced by PRs; Trivy scans the built container including OS packages.

uv is the only dependency/package manager. The project uses standard PEP 621 metadata and PEP 735 dependency groups and the native `uv_build` backend, so it can produce a normal wheel/sdist and can later evolve into a uv workspace if extensions become independently packaged plugins.

## AI coding setup

- `CLAUDE.md`: concise always-loaded Claude Code repository rules.
- `.claude/settings.json`: project permissions, secret protection, shell sandbox, and destructive-command restrictions.
- `.claude/rules/`: path-aware Python/Django/security/architecture guidance.
- `.claude/skills/`: reusable `/review`, `/quality`, `/fix` workflows.
- `.claude/agents/`: read-only code, security, and architecture reviewers.
- `AGENTS.md`: repository instructions for Codex.
- `.agents/skills/`: Codex `$review`, `$quality`, `$fix` skills.
- `.codex/config.toml`: project-level agent concurrency without overriding user model/approval choices.
- `.codex/agents/`: read-only Codex code/security/architecture specialists.
- `docs/ai/`: normative architecture + infrastructure/persistence contracts plus shared standards, security policy, tooling rationale, and source references.
- `docs/adr/0001-data-mapper-over-django-orm.md`: accepted persistence decision and rationale.

The root instruction files deliberately stay compact; repeatable procedures and detailed policy live in skills/docs. Both agents are instructed to use the same Make targets, so CI, humans, Claude, and Codex share one executable definition of completion.

Claude's Bash sandbox is intended for macOS, Linux, and WSL2. On Windows, run the repository/Claude Code in WSL2 rather than weakening the committed project guardrails.

## Project layout

```text
src/strata_cms/
├── domain/
│   └── ...                 # plain Python entities/value objects/rules (Content, Revision, ContentRoute)
├── application/
│   ├── ports/              # repositories/UoW/cache/search/authorization/event/task/etc.
│   ├── content/             # content write use cases, Delivery read service, search indexing
│   └── routing/             # page-tree (ContentRoute) use cases and path resolution
├── infrastructure/
│   ├── persistence/django/ # Django ORM Records, mappers, repos, UoW, search backend, routing
│   ├── authorization/      # shared ContentAuthorizationPolicy + Django-actor builder
│   ├── cache/               # default Django cache adapter
│   ├── clock/               # system clock adapter
│   ├── tasks/                # framework-agnostic outbox worker loop
│   ├── search/               # empty: the concrete adapter lives under persistence/django/search.py
│   └── messaging/            # empty: no external broker adapter is wired yet
├── api/                    # DRF presentation adapters (Delivery + Management)
├── admin/                  # Django Admin/Unfold presentation adapter
├── config/                 # settings, URLs, ASGI/WSGI, composition root
└── py.typed
```

The starter defines provider-neutral ports for Clock, cache, search,
authorization, durable messages, integration events, tasks and Unit of Work.
The full content vertical is implemented: stable Content aggregates,
immutable Revision snapshots, publish/archive/restore lifecycle, a shared
authorization policy, a page-tree (`ContentRoute`) with path resolution, a
PostgreSQL-backed search index (SQLite `icontains` fallback for lightweight
local/test runs) kept in sync via the outbox worker, and both a public
Delivery API and an authenticated Management API built on the same use
cases. `infrastructure/search/` and `infrastructure/messaging/` remain empty
stub packages — search's concrete adapter lives alongside the other Django
persistence adapters (`infrastructure/persistence/django/search.py`), and no
external message-broker adapter has been built yet (the outbox/worker use
PostgreSQL directly).

Django ORM is deliberately confined to infrastructure. Domain entities are
plain Python objects; repositories and explicit mappers bridge them to Django
`*Record` models. Read-heavy paths may use query-service DTOs rather than
hydrating entities. `make architecture-check` enforces the import-level portion
of these boundaries.

## CMS architecture

The architecture contract is now defined in `docs/ai/architecture.md`. The core direction is a **headless-first modular monolith with a stable plugin contract**:

- code-defined content types/plugins plus versioned structured blocks rather than runtime-created Django models;
- stable UUID content identities and namespaced type/block keys;
- immutable versioned revisions with strict draft/published separation; the
  concrete model is documented in ADR 0002;
- Page as one content capability, not the superclass for every CMS object;
  routing is an optional attached `ContentRoute` per ADR 0006, not a field
  every content item carries;
- ADR 0003 compiled plugin registry: startup-only builder, dependency/version validation, deterministic ordering, immutable runtime lookup and Django system-check validation;
- public `strata_cms.plugin_api`, typed content schemas, pure in-memory historical migrations, and current-schema normalization on new writes;
- ADR 0004 structured blocks: revision-embedded stable UUID/type/version/data envelopes, named nested slots, independent block migrations, recursive validation/Delivery serialization, and declared cross-plugin block dependencies;
- ADR 0005 schema-driven management editing: optional presentation-neutral editor metadata, ephemeral working documents, one Management API write path, and Unfold Admin as a client of the same use cases;
- a shared `ContentAuthorizationPolicy` decides every privileged action once,
  called from the application use cases rather than duplicated per adapter;
  publish authority (`publish_contentrecord`) is a distinct permission from
  edit authority (`change_contentrecord`);
- Delivery and Management APIs with different trust/state semantics, both
  rate-limited (`ScopedRateThrottle`);
- rebuildable published projections for routing (`RoutePathRecord`, ADR 0006)
  and search (`SearchDocumentRecord`), kept in sync via the outbox worker;
- PostgreSQL + storage as the minimal production infrastructure, with a
  queue/broker beyond PostgreSQL remaining optional;
- Data Mapper persistence: plain entities + repositories + Unit of Work over Django ORM records;
- narrow infrastructure ports for cache/search/authorization/events/tasks/messages/storage/time;
- at-least-once durable messaging, idempotent handlers, and transactional outbox for reliable integration events;
- an opt-in PostgreSQL-backed `strata_worker` (`python manage.py strata_worker`,
  wired into `docker-compose.yml` as its own service), while the web process
  never requires it to start; Celery/RabbitMQ/etc. remain replaceable adapters.

The detailed infrastructure contract lives in `docs/ai/infrastructure.md`. ADR
`0001` records the Data Mapper decision, ADR `0002` records the concrete
Content/Revision aggregate, ADR `0003` records the plugin/content registry,
ADR `0004` records structured block semantics, ADR `0005` records the
management/editor contract, and ADR `0006` records content routing (the
optional attached `ContentRoute` tree and its synchronously-rebuilt path
projection). Import Linter contracts are active for the current
domain/application/persistence seams. As independently distributable plugins or
feature-private packages appear, extend those contracts rather than relying on
convention alone. uv workspaces remain a natural future evolution if plugins
become separately packaged.

## Plugin/content registry

The plugin model is implemented as a compiled registry, documented in ADR 0003.
A practical third-party authoring walkthrough is in `docs/plugins.md`.
`StrataRegistryBuilder` accepts declarative plugin/content registrations during
startup, validates plugin API/CMS/dependency versions and dependency cycles, then
produces an immutable `StrataRegistry`. The Django adapter gathers installed
`StrataPluginConfig` applications centrally and gives each one an owner-scoped
`PluginRegistrar`; plugins do not mutate a global registry from
`AppConfig.ready()`. `manage.py check` compiles the graph.

Third-party contracts are exported from `strata_cms.plugin_api`. A content type
uses a typed `ContentSchema[T]`, a stable `ContentTypeKey`, an independent
persisted schema version, and a complete chain of pure adjacent migrations. Old
revision JSON is migrated only in memory when read. New writes pass through the
application `ContentTypeService` port and are persisted in the current canonical
schema.

`strata_cms.examples.simple_article` is intentionally **not installed by
default**; it is a small reference plugin demonstrating v1→v2 content migration,
typed validation and Delivery serialization. The same example registration also
includes `strata_cms.examples.structured_page`, which demonstrates a migrated
text block, a container with a named nested slot, a block-backed content field,
and recursive block Delivery serialization. The examples now also publish generic
editor metadata consumed by the Management API and Unfold editor. None of these
example content types become required CMS content.

## Management editing

The authenticated Management API under `/api/v1/manage/` exposes content-type
editor discovery, latest working revisions plus full revision history,
revision creation, publication, archive/restore, and page-tree route
attach/move/detach. Authorization is decided once by the shared
`ContentAuthorizationPolicy` (Django staff status plus the specific
permission mapped to the requested action — publish is its own permission,
separate from edit); object/site/subtree-scoped policy beyond that remains a
separate future evolution. Writes always use optimistic content versions and
the same application use cases as other adapters.

The Unfold Admin registers `ContentRecord` only for listing/discovery. Its Add
and Change flows render the schema-driven generic editor rather than Django's
model form. Scalar fields come from semantic editor hints; structured blocks can
be added, removed, reordered and nested through declared named slots. The
working tree exists only in the browser until Save appends an immutable
revision. Admin does not call `ModelForm.save()`/`save_model()` to mutate CMS
state; Django's own record-delete UI stays disabled (hard-deleting a
`ContentRecord` would cascade-delete its immutable revision history), but the
changelist exposes "Archive selected"/"Restore selected" bulk actions that
call the real `archive_content`/`restore_content` application use cases.

## CI/security

The repository includes:
- main CI with Python 3.14 full quality checks and Python 3.12/3.13 compatibility tests;
- package build validation;
- Docker build + HIGH/CRITICAL Trivy scan;
- CodeQL `security-extended` analysis;
- PR dependency review at moderate severity and above;
- Dependabot for uv, pre-commit, GitHub Actions, and Docker.

Publishing/deployment automation is intentionally absent until a deployment environment is selected.

## Lockfile note

This starter does not fabricate `uv.lock`: resolution must happen against the real package index. Run `make bootstrap` once after unpacking, inspect the resolved versions, then commit `uv.lock`. From that point onward, `make check`, CI, Docker, and agent workflows require the committed lockfile.

## Outbox worker

Reliable publication/archive/restore events enter the PostgreSQL
transactional outbox in the same Unit of Work as the authoritative content
pointer update. `python manage.py strata_worker` claims and processes them:
`SELECT ... FOR UPDATE SKIP LOCKED` for safe multi-worker claiming,
visibility-timeout lease recovery, exponential-backoff retry, and an explicit
dead-letter state after `--max-attempts`. It is opt-in — the web process
never requires it to start — but `docker-compose.yml` runs it as its own
`worker` service by default.

The default dispatcher only logs; pass
`--dispatcher strata_cms.config.services.dispatch_content_event` to also keep
the search index (`SearchDocumentRecord`) in sync with publish/archive/restore
events. Celery or external brokers remain adapters to the public task/message
contracts rather than dependencies in domain/application code.
