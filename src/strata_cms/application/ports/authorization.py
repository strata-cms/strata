"""Application-owned policy boundary for privileged content actions.

Enforced once, inside the shared use cases, so Admin/API/CLI/worker callers
cannot drift into separate ad hoc permission checks.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from strata_cms.domain.value_objects import ActorId


class ContentAction(Enum):
    """A privileged action a caller may request against content."""

    VIEW = "view"
    CREATE = "create"
    CHANGE = "change"
    PUBLISH = "publish"
    ARCHIVE = "archive"
    RESTORE = "restore"


@dataclass(frozen=True, slots=True)
class ContentActor:
    """Authenticated actor identity plus the permission set a policy consults."""

    id: ActorId
    is_staff: bool
    permissions: frozenset[str]


class ContentAuthorizationPolicy(Protocol):
    """Decide whether one actor may perform one action against content."""

    def authorize(self, actor: ContentActor, action: ContentAction) -> None:
        """Raise `NotAuthorizedError` when the actor may not perform the action."""
        ...  # pragma: no cover - protocol declaration
