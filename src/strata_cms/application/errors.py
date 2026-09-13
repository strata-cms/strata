"""Application use-case errors safe for presentation adapters to translate."""

from dataclasses import dataclass

from strata_cms.domain.value_objects import ContentId, ContentTypeKey, RevisionId


class ApplicationError(Exception):
    """Base class for expected application/use-case failures."""


class NotAuthorizedError(ApplicationError, PermissionError):
    """Raised when an actor may not perform a requested content action."""

    def __init__(self, action: str) -> None:
        """Capture the denied action for presentation adapters."""
        super().__init__(f"Not authorized to perform action '{action}'.")
        self.action = action


class ContentNotFoundError(ApplicationError, LookupError):
    """Raised when a requested content item does not exist."""

    def __init__(self, content_id: ContentId) -> None:
        """Capture the missing content identity for presentation adapters."""
        super().__init__(f"Content '{content_id}' was not found.")
        self.content_id = content_id


class RevisionNotFoundError(ApplicationError, LookupError):
    """Raised when a requested revision does not exist."""

    def __init__(self, revision_id: RevisionId) -> None:
        """Capture the missing revision identity for presentation adapters."""
        super().__init__(f"Revision '{revision_id}' was not found.")
        self.revision_id = revision_id


class ContentTypeUnavailableError(ApplicationError, LookupError):
    """Raised when persisted/requested content has no installed type handler."""

    def __init__(self, type_key: ContentTypeKey) -> None:
        """Capture the unavailable content type key for presentation adapters."""
        super().__init__(f"Content type '{type_key}' is not available.")
        self.type_key = type_key


@dataclass(frozen=True, slots=True)
class ContentDataProblem:
    """Stable application-facing validation detail for presentation adapters."""

    code: str
    message: str
    path: str = "$"


class InvalidContentDataError(ApplicationError, ValueError):
    """Raised when content data cannot be decoded, migrated, or validated."""

    def __init__(
        self,
        *,
        type_key: ContentTypeKey,
        problems: tuple[ContentDataProblem, ...],
    ) -> None:
        """Capture the failing type key and structured problems."""
        super().__init__(f"Content data for '{type_key}' is invalid.")
        self.type_key = type_key
        self.problems = problems


class RouteAlreadyAttachedError(ApplicationError, ValueError):
    """Raised when attaching a route to content that already has one."""

    def __init__(self, content_id: ContentId) -> None:
        """Capture the already-routed content identity for presentation adapters."""
        super().__init__(f"Content '{content_id}' already has a route.")
        self.content_id = content_id


class RouteNotFoundError(ApplicationError, LookupError):
    """Raised when a requested content item has no attached route."""

    def __init__(self, content_id: ContentId) -> None:
        """Capture the missing route's content identity for presentation adapters."""
        super().__init__(f"Content '{content_id}' has no route.")
        self.content_id = content_id


class SlugConflictError(ApplicationError, ValueError):
    """Raised when a parent/slug pair is already used by a sibling route."""

    def __init__(self, *, parent_id: ContentId | None, slug: str) -> None:
        """Capture the conflicting parent/slug for presentation adapters."""
        super().__init__(f"Slug '{slug}' is already used under parent '{parent_id}'.")
        self.parent_id = parent_id
        self.slug = slug


class RouteHasChildrenError(ApplicationError, ValueError):
    """Raised when detaching a route that still has children."""

    def __init__(self, content_id: ContentId) -> None:
        """Capture the non-empty route's content identity for presentation adapters."""
        super().__init__(f"Content '{content_id}' still has child routes.")
        self.content_id = content_id
