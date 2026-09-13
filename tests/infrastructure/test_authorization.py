import pytest

from strata_cms.application.errors import NotAuthorizedError
from strata_cms.application.ports.authorization import ContentAction, ContentActor
from strata_cms.domain.value_objects import ActorId
from strata_cms.infrastructure.authorization.policy import StaffPermissionContentPolicy

POLICY = StaffPermissionContentPolicy()
ACTOR_ID = ActorId("user:1")


def test_staff_with_required_permission_is_authorized() -> None:
    actor = ContentActor(
        id=ACTOR_ID,
        is_staff=True,
        permissions=frozenset({"strata_persistence.publish_contentrecord"}),
    )

    POLICY.authorize(actor, ContentAction.PUBLISH)


def test_non_staff_is_never_authorized_even_with_permission() -> None:
    actor = ContentActor(
        id=ACTOR_ID,
        is_staff=False,
        permissions=frozenset(
            {
                "strata_persistence.publish_contentrecord",
                "strata_persistence.change_contentrecord",
            }
        ),
    )

    with pytest.raises(NotAuthorizedError):
        POLICY.authorize(actor, ContentAction.PUBLISH)


def test_staff_without_required_permission_is_denied() -> None:
    actor = ContentActor(
        id=ACTOR_ID,
        is_staff=True,
        permissions=frozenset({"strata_persistence.change_contentrecord"}),
    )

    with pytest.raises(NotAuthorizedError):
        POLICY.authorize(actor, ContentAction.PUBLISH)


def test_publish_and_change_require_distinct_permissions() -> None:
    editor = ContentActor(
        id=ACTOR_ID,
        is_staff=True,
        permissions=frozenset({"strata_persistence.change_contentrecord"}),
    )

    POLICY.authorize(editor, ContentAction.CHANGE)
    with pytest.raises(NotAuthorizedError):
        POLICY.authorize(editor, ContentAction.PUBLISH)
