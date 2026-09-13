UV ?= uv
RUN := $(UV) run --locked
PYTHON := $(RUN) python
SCHEMA_OUT ?= /tmp/strata-openapi.yaml
AUDIT_REQUIREMENTS ?= /tmp/strata-audit-requirements.txt

.PHONY: bootstrap install metadata-check format format-check lint architecture-check typecheck test test-fast django-check migration-check schema schema-check security check run migrate migrations superuser package-build docker-build docker-up docker-down

bootstrap:
	$(UV) lock
	$(UV) sync
	$(RUN) pre-commit install

install:
	$(UV) sync --locked
	$(RUN) pre-commit install

metadata-check:
	$(UV) lock --check
	$(UV) sync --locked
	$(UV) pip check

format:
	$(RUN) ruff check --fix src tests manage.py
	$(RUN) ruff format src tests manage.py

format-check:
	$(RUN) ruff format --check src tests manage.py

lint:
	$(RUN) ruff check src tests manage.py

architecture-check:
	$(RUN) import-linter lint

typecheck:
	$(RUN) mypy src/strata_cms tests

test:
	$(RUN) pytest

test-fast:
	$(RUN) pytest -n auto

django-check:
	$(PYTHON) manage.py check --settings=strata_cms.config.settings.test

migration-check:
	$(PYTHON) manage.py makemigrations --check --dry-run --settings=strata_cms.config.settings.test

schema:
	$(PYTHON) manage.py spectacular --file openapi.yaml --validate --fail-on-warn --settings=strata_cms.config.settings.test

schema-check:
	$(PYTHON) manage.py spectacular --file $(SCHEMA_OUT) --validate --fail-on-warn --settings=strata_cms.config.settings.test

security:
	$(RUN) ruff check --select S src tests manage.py
	$(UV) export --no-emit-project --no-hashes -o $(AUDIT_REQUIREMENTS)
	$(RUN) pip-audit --strict -r $(AUDIT_REQUIREMENTS)
	DJANGO_SECRET_KEY='ci-only-secret-key-please-replace-01234567890123456789' \
	DJANGO_ALLOWED_HOSTS='example.invalid' \
	DATABASE_URL='sqlite:///:memory:' \
	DJANGO_SECURE_SSL_REDIRECT='true' \
	DJANGO_SECURE_HSTS_SECONDS='31536000' \
	$(PYTHON) manage.py check --deploy --fail-level WARNING --settings=strata_cms.config.settings.production

check: metadata-check format-check lint architecture-check typecheck django-check migration-check schema-check test

run:
	$(PYTHON) manage.py runserver 0.0.0.0:8000

migrate:
	$(PYTHON) manage.py migrate

migrations:
	$(PYTHON) manage.py makemigrations

superuser:
	$(PYTHON) manage.py createsuperuser

package-build:
	$(UV) build

docker-build:
	docker build --pull -t strata:local .

docker-up:
	docker compose up --build

docker-down:
	docker compose down
