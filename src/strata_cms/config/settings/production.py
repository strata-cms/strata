"""Production settings. All sensitive values come from the environment."""

from django.core.exceptions import ImproperlyConfigured

from .base import *
from .base import env

SECRET_KEY = env.str("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
DEBUG = False
DATABASES = {"default": env.db("DATABASE_URL")}

if not SECRET_KEY or not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Production secret key and allowed hosts are required")

SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
# Only meaningful once HSTS itself is enabled; this sets the header directive
# only. Actually submitting the domain to browsers' preload lists is a
# separate, hard-to-reverse operational step at https://hstspreload.org.
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0

# Set this only when Django is behind a trusted proxy that overwrites this header.
if env.bool("DJANGO_TRUST_PROXY_SSL_HEADER", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
