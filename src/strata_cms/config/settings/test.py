"""Automated test settings."""

from .base import *

SECRET_KEY = "test-only-key-not-used-outside-test-suite"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

INSTALLED_APPS += [
    "strata_cms.examples.apps.ExampleArticlePluginConfig",
]

# Manifest static storage requires a prior `collectstatic` build step that the
# test suite has no reason to depend on; use plain storage so admin templates
# referencing `{% static %}` render without a build artifact.
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
