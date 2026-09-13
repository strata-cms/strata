# Tooling policy

This file records deliberate choices so humans and coding agents do not add overlapping tools without an explicit reason.

## Runtime and framework

- Supported Python: 3.12, 3.13, 3.14. Python 3.14 is the default runtime/container; CI verifies older supported minors.
- Django 5.2 LTS is the framework baseline.
- Django REST Framework is the API layer.
- django-unfold is the admin presentation layer; retain Django admin conventions rather than introducing a separate admin SPA without a requirement.
- drf-spectacular owns OpenAPI schema generation and validation.
- PostgreSQL is the production database; local Compose follows the current stable PostgreSQL major.

## Dependency, environment, and packaging workflow

uv is the single project/dependency manager. `pyproject.toml` uses standard PEP 621 project metadata and PEP 735 dependency groups; `uv.lock` is committed after initial resolution. The native `uv_build` backend builds the pure-Python wheel/sdist.

Do not add Poetry, pip-tools, Pipenv, PDM, Hatch project management, or parallel requirements lockfiles. Export formats may be generated transiently for integrations, but `uv.lock` remains authoritative.

Use:

```bash
uv add <package>
uv remove <package>
uv lock --check
uv sync --locked
uv run --locked <command>
uv build
```

Do not hand-edit `uv.lock`.

## Quality tool ownership

| Concern | Owner |
| --- | --- |
| Formatting | Ruff formatter |
| Import ordering | Ruff `I` rules |
| Lint/correctness/modernization/Django rules | Ruff |
| Fast source security heuristics | Ruff `S` rules |
| Static typing | mypy + django-stubs + DRF stubs |
| Architecture/import boundaries | Import Linter |
| Behavior | pytest + pytest-django |
| Coverage | pytest-cov / coverage.py |
| Property-based tests where useful | Hypothesis |
| Optional parallel local tests | pytest-xdist |
| OpenAPI contract generation | drf-spectacular |
| Dependency vulnerabilities | pip-audit |
| Deep source/data-flow security analysis | GitHub CodeQL |
| PR supply-chain changes | GitHub Dependency Review |
| Container/OS/dependency image vulnerabilities | Trivy |
| Local hook orchestration | pre-commit |
| CI | GitHub Actions |

`make check` is the canonical normal gate. `make security` is the locally reproducible security gate. CI adds checks that require GitHub/container context.

## Why Ruff replaces Black/isort/Pylint/Bandit locally

Ruff's formatter is designed as a Black replacement, its linter implements isort-style import ordering plus many Flake8/Pylint/Django/security rule families, and it runs quickly enough to be a commit-time gate. Running Black, isort, Pylint, Bandit, and Ruff together would duplicate ownership and create conflicting policy.

Ruff does not replace mypy: typing remains semantic analysis with Django-aware stubs. Ruff security rules also do not replace CodeQL or dependency/container vulnerability scanning.

The repository intentionally avoids formatter-conflicting Ruff rules such as quote/comma enforcement that fight the formatter. Add/disable rules because of signal quality, not to make a single patch convenient.

## Type checking policy

mypy is intentionally strict without using one global `strict = true` switch. The explicit settings encode the desired invariants while allowing framework-specific exceptions to remain visible and narrow. CI has one canonical type checker; editor Pyright/Pylance use is fine but is not a second merge gate.

## Testing policy

Canonical semantics are `pytest` without xdist. `make test-fast` is an optimization for local iteration and must not be used to hide ordering/isolation bugs. Hypothesis is available selectively for logic where generated edge cases provide meaningful additional assurance.

Coverage is a backstop, not the goal. Keep the project floor, but prioritize regression tests, changed-code behavior, negative authorization/input cases, and security invariants.

## OpenAPI policy

Every public API change must keep:

```bash
make schema-check
```

warning-free. drf-spectacular annotations are part of the public contract. Inspect schema diffs for externally visible API changes; never silence schema warnings globally to make CI green.

## Supply-chain policy

- `pip-audit` remains the stable local Python vulnerability scanner.
- uv's own `audit` command is not a required gate while it is a preview feature.
- Dependabot uses the native `uv` ecosystem and also updates Actions/Docker/pre-commit references.
- Dependency Review fails PRs that introduce moderate-or-higher known vulnerabilities.
- CodeQL runs `security-extended` queries.
- Trivy fails the image build gate on HIGH/CRITICAL findings with fixes available (`ignore-unfixed` is enabled to avoid impossible gates; exceptions still require review).

## Architecture linting

Import Linter is a required development dependency and part of `make check`.
The current contracts in `pyproject.toml` enforce that:

- domain cannot import application, infrastructure, presentation/config, Django,
  or DRF;
- application cannot import concrete infrastructure, presentation/config,
  Django, or DRF;
- the Django persistence adapter is protected from direct use outside allowed
  infrastructure/Admin/config seams.

Use `make architecture-check` while working on boundary-affecting changes. The
contracts intentionally encode import direction, not every semantic rule: code
review still verifies that repositories return entities rather than records,
Unit of Work owns transactions, query services do not leak QuerySets/provider
syntax, and Admin/API actions do not duplicate Active Record workflows.

Do not add broad `ignore_imports` or weaken contracts simply to get a change
through CI. If a legitimate integration requires a new dependency direction,
update the architecture documentation first and make the narrowest executable
change with tests/review.

As feature/plugin packages emerge, extend contracts for feature independence and
protected private internals rather than relying on convention alone.
