"""Build the application-layer actor context from an authenticated Django user."""

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser

from strata_cms.application.ports.authorization import ContentActor
from strata_cms.domain.value_objects import ActorId


def build_content_actor(user: AbstractBaseUser | AnonymousUser) -> ContentActor:
    """Translate a Django request.user into a policy-ready actor.

    Callers must have already rejected unauthenticated requests (e.g. via the
    Management permission class); an AnonymousUser here is a caller bug.
    """
    if not user.is_authenticated or user.pk is None:
        raise RuntimeError("build_content_actor requires an authenticated user.")
    permissions = frozenset(user.get_all_permissions())  # type: ignore[attr-defined]
    return ContentActor(
        id=ActorId(str(user.pk)),
        is_staff=bool(getattr(user, "is_staff", False)),
        permissions=permissions,
    )
