# Source guidance used for this starter

The project rules were synthesized from:

## Python and Django standards

- PEP 8 — https://peps.python.org/pep-0008/
- PEP 257 — https://peps.python.org/pep-0257/
- Hitchhiker's Guide to Python: Code Style — https://docs.python-guide.org/writing/style/
- OpenSSF Secure Coding Guide for Python — https://best.openssf.org/Secure-Coding-Guide-for-Python/
- OWASP Django Security Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Django_Security_Cheat_Sheet.html
- OWASP REST Security Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html
- Django security/deployment documentation — https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- Rui Maranhão's Python best-practices gist — https://gist.github.com/ruimaranhao/4e18cbe3dad6f68040c32ed6709090a3
- Somraj Saha/Jarmos standard Python CI/CD article supplied by the project owner.

## Tooling

- uv project management — https://docs.astral.sh/uv/concepts/projects/
- uv dependency locking/sync — https://docs.astral.sh/uv/concepts/projects/sync/
- uv Docker integration — https://docs.astral.sh/uv/guides/integration/docker/
- Ruff linter — https://docs.astral.sh/ruff/linter/
- Ruff formatter — https://docs.astral.sh/ruff/formatter/
- mypy — https://mypy.readthedocs.io/
- django-stubs — https://github.com/typeddjango/django-stubs
- pytest-django — https://pytest-django.readthedocs.io/
- Hypothesis — https://hypothesis.readthedocs.io/
- pip-audit — https://github.com/pypa/pip-audit
- drf-spectacular — https://drf-spectacular.readthedocs.io/
- Django Unfold quickstart/ModelAdmin — https://unfoldadmin.com/docs/installation/quickstart/
- Django Unfold ModelAdmin options — https://unfoldadmin.com/docs/configuration/modeladmin/
- Import Linter — https://import-linter.readthedocs.io/
- GitHub CodeQL — https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql
- GitHub Dependency Review — https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/about-dependency-review
- Trivy — https://trivy.dev/

## Agent configuration

- Claude Code memory/project instructions — https://code.claude.com/docs/en/memory
- Claude Code settings/permissions — https://code.claude.com/docs/en/settings
- Claude Code sandboxing — https://code.claude.com/docs/en/sandboxing
- Claude Code subagents — https://code.claude.com/docs/en/sub-agents
- Claude Code skills — https://code.claude.com/docs/en/skills
- OpenAI Codex AGENTS.md guidance — https://learn.chatgpt.com/docs/agent-configuration/agents-md
- OpenAI Codex skills — https://learn.chatgpt.com/docs/build-skills
- OpenAI Codex subagents — https://learn.chatgpt.com/docs/agent-configuration/subagents
- OpenAI Codex project configuration — https://learn.chatgpt.com/docs/codex/config-reference

These URLs are reference material, not a substitute for the repository's
explicit rules. If an upstream recommendation conflicts with a newer framework
security fix or a project-specific requirement, prefer the secure/current
framework behavior and document the decision.
