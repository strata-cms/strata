# Engineering Standards

This is the detailed shared reference for human developers, Claude Code, and Codex.

## Principles
1. Correctness before cleverness.
2. Readability is a feature.
3. Explicit dependencies and control flow beat hidden behavior.
4. Keep modules cohesive and public interfaces small.
5. Security and authorization are design constraints, not post-processing.
6. Externally observable behavior should be testable.
7. Prefer reversible, incremental changes.

## Python
Follow PEP 8 and PEP 257 plus the Python Guide style guidance. In particular:
- four-space indentation, UTF-8, LF endings;
- `snake_case` functions/modules/variables, `PascalCase` classes/exceptions, uppercase constants;
- one logical statement per line;
- no wildcard imports in application code; split-settings `from .base import *` is the repository exception;
- standard-library / third-party / first-party import grouping, owned by Ruff;
- descriptive names; one-letter names only in tiny obvious scopes;
- context managers for resources;
- specific exception types and clear failure semantics;
- no mutable defaults or accidental module-level mutable state;
- readable comprehensions; iterators/generators when large materialization is unnecessary;
- avoid speculative abstractions and metaprogramming.

Ruff is authoritative for formatting/import ordering/lint policy. Do not manually fight the formatter or duplicate its responsibility with another formatter/linter.

## Typing
- Public functions/methods, services/selectors, serializer helpers, and reusable internal APIs require annotations.
- Prefer precise types, protocols, generics, `TypedDict`, and dataclasses over `dict[str, Any]` when structure matters.
- Narrow optionals before use.
- `cast()` is for runtime facts the checker cannot infer, not to silence inconvenient errors.
- `# type: ignore[code]` must be narrow and justified when non-obvious.
- Avoid exporting untyped third-party leakage through public interfaces.
- Write code valid for the lowest supported Python minor (3.12) unless the supported range is intentionally changed.

## Django / architecture layout
`src/strata_cms/config/` is the Django composition root. The main architectural
seams are `domain/`, `application/`, `infrastructure/`, `api/`, and `admin/`.
See `docs/ai/architecture.md` and `docs/ai/infrastructure.md` for normative
boundaries.

- Domain: plain Python entities/value objects/domain rules; no Django/DRF.
- Application: use cases, commands/queries, repository/UoW/infrastructure ports.
- Infrastructure: Django ORM records/repositories/mappers/query adapters and
  concrete cache/search/message/task/storage/clock adapters.
- API/Admin: presentation adapters calling application use cases.
- Config/bootstrap: wiring and framework settings.

Do not create giant generic `models.py`, `services.py`, or `utils.py` dumping
grounds. Group cohesive behavior by feature/aggregate within the architectural
seam. Do not create layers or abstractions with no current behavior merely for
symmetry.

Django persistence records are not domain entities. Prefer `*Record` names and
keep Active Record operations inside the persistence adapter.

## Transactions and data integrity
- Express invariants in database constraints where possible.
- Application use cases express multi-write transaction intent through a Unit of Work port; the Django persistence adapter implements it with `transaction.atomic()`.
- Use `select_for_update()`/locking inside Django persistence adapters for concurrent transitions that cannot tolerate lost updates.
- Avoid network calls inside DB transactions.
- Use explicit ordering for pagination/stable result sets.
- Choose deletion semantics (`PROTECT`, `RESTRICT`, `CASCADE`, `SET_NULL`) deliberately.

## API design
- Base path: `/api/v1/`.
- JSON is the default public representation.
- Use DRF serializers for boundary validation.
- Explicitly declare exposed/writable fields; avoid mass assignment/over-posting.
- Paginate unbounded collections.
- Return semantic status codes and stable error structures.
- Never treat opaque IDs as authorization.
- Breaking client changes require a new API version or explicitly approved migration plan.
- drf-spectacular annotations and generated OpenAPI are part of the API contract; schema generation must be warning-free.

## Admin / Unfold
- `unfold` appears before `django.contrib.admin` in `INSTALLED_APPS`.
- Admin may register Django persistence records, but custom business operations call application use cases; do not implement domain workflows through record `.save()`/admin-specific mutation code.
- Admin classes inherit from `unfold.admin.ModelAdmin` or appropriate Unfold inline classes.
- Admin UI is not an authorization substitute: permissions and validation remain server-side.
- Optimize list pages against N+1 queries.
- Prefer readonly/system-owned fields and explicit fieldsets for sensitive values.
- Review bulk admin actions for authorization, transactional integrity, and auditability.

## Testing
- pytest is canonical; tests are deterministic and order/network independent.
- Bug fixes should add regression tests.
- New behavior should cover success, invalid input, permission denial, and important edge cases.
- Domain tests should normally need no Django DB. Application tests may use fake repositories/UoW/ports; persistence integration tests verify mappings, transactions, locking and query behavior.
- Mock/fake external boundaries rather than the unit's own internals.
- Hypothesis is encouraged where generated examples test meaningful invariants or parser/validator edge cases.
- xdist is a speed optimization; code must also pass canonical non-parallel semantics.
- Coverage percentage is a floor, not a substitute for behavioral assertions.

## Logging and observability
- Use `logger = logging.getLogger(__name__)`.
- Never log secrets, tokens, passwords, session identifiers, Authorization headers, or unnecessary personal data.
- Log actionable context, not raw untrusted payloads by default.
- Log exceptions at the boundary that can meaningfully handle/report them; avoid duplicate stack traces.

## Documentation
Document architectural decisions, invariants, public APIs, and extension points, not obvious syntax. Integrators should be able to use a public extension point without reading its private implementation.

## Tool responsibilities
- uv: dependencies, environments, locking, builds.
- Ruff: format/import/lint/modernization/Django/security heuristics.
- mypy + stubs: static typing.
- pytest stack: behavior and coverage; Hypothesis/xdist selectively.
- drf-spectacular: OpenAPI contract.
- pip-audit: Python dependency vulnerabilities.
- Django `check --deploy`: framework deployment sanity.
- CodeQL: deeper CI source analysis.
- Dependency Review: PR dependency-risk gate.
- Trivy: built-image vulnerability scan.
- Import Linter: executable dependency/persistence boundary contracts.
- pre-commit: fast local orchestration.
- Docker build: deployable runtime artifact.

Avoid adding overlapping mandatory tools unless the additional tool catches a clearly distinct class of defects.
