"""Default content authorization policy: staff status plus a Django permission.

Publication authority is deliberately separate from edit authority (a distinct
`publish_contentrecord` permission), per the documented CMS invariant that
editing and publishing are different levels of trust. Object/site/subtree
scoping is intentionally out of scope for this default policy.
"""

from strata_cms.application.errors import NotAuthorizedError
from strata_cms.application.ports.authorization import ContentAction, ContentActor

_REQUIRED_PERMISSION: dict[ContentAction, str] = {
    ContentAction.VIEW: "strata_persistence.view_contentrecord",
    ContentAction.CREATE: "strata_persistence.add_contentrecord",
    ContentAction.CHANGE: "strata_persistence.change_contentrecord",
    ContentAction.PUBLISH: "strata_persistence.publish_contentrecord",
    ContentAction.ARCHIVE: "strata_persistence.delete_contentrecord",
    ContentAction.RESTORE: "strata_persistence.change_contentrecord",
}


class StaffPermissionContentPolicy:
    """Require staff status plus the Django permission mapped to the action."""

    def authorize(self, actor: ContentActor, action: ContentAction) -> None:
        """Raise `NotAuthorizedError` unless the actor holds the mapped permission."""
        required = _REQUIRED_PERMISSION[action]
        if not actor.is_staff or required not in actor.permissions:
            raise NotAuthorizedError(action.value)
