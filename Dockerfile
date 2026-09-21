# syntax=docker/dockerfile:1
FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock .//
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
COPY manage.py ./manage.py
COPY README.md ./README.md
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    DJANGO_SETTINGS_MODULE=strata_cms.config.settings.test
RUN python manage.py collectstatic --noinput

FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=strata_cms.config.settings.production

RUN addgroup --system strata && adduser --system --ingroup strata --home /app strata
WORKDIR /app

COPY --from=builder --chown=strata:strata /app/.venv /app/.venv
COPY --from=builder --chown=strata:strata /app/staticfiles /app/staticfiles
COPY --chown=strata:strata src ./src
COPY --chown=strata:strata manage.py ./manage.py

RUN mkdir -p /app/media && chown -R strata:strata /app
USER strata

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/', timeout=2)" || exit 1

CMD ["gunicorn", "strata_cms.config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "--error-logfile", "-"]
