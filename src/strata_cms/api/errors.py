"""Client-safe error details for API responses.

Exception text is for logs and developers: it can embed identifiers, slugs or
internals that change as use cases evolve. API responses therefore use fixed
messages selected by exception type and never interpolate ``str(exception)``.
"""

from strata_cms.application.errors import (
    ContentNotFoundError,
    ContentTypeUnavailableError,
    InvalidContentDataError,
    NotAuthorizedError,
    RevisionNotFoundError,
    RouteAlreadyAttachedError,
    RouteHasChildrenError,
    RouteNotFoundError,
    SlugConflictError,
)
from strata_cms.domain.errors import (
    ConcurrentModificationError,
    ContentArchivedError,
    InvalidContentTypeKeyError,
    RevisionOwnershipError,
    RouteCycleError,
)

DEFAULT_ERROR_DETAIL = "The request could not be processed."

_PUBLIC_DETAILS: tuple[tuple[type[Exception], str], ...] = (
    (NotAuthorizedError, "Not authorized to perform this action."),
    (ContentNotFoundError, "Content was not found."),
    (RevisionNotFoundError, "Revision was not found."),
    (RouteNotFoundError, "Route was not found."),
    (ContentTypeUnavailableError, "Content type is not available."),
    (InvalidContentDataError, "Content data is invalid."),
    (
        InvalidContentTypeKeyError,
        "Content type keys must be <= 200 chars and use lowercase namespaced "
        "identifiers such as 'acme_blog.article'.",
    ),
    (
        ConcurrentModificationError,
        "The resource changed since the supplied version.",
    ),
    (ContentArchivedError, "Content is archived and must be restored first."),
    (RouteAlreadyAttachedError, "Content already has a route."),
    (SlugConflictError, "Slug is already used under this parent."),
    (RouteHasChildrenError, "Content still has child routes."),
    (RouteCycleError, "Content cannot be moved under itself or a descendant."),
    (
        RevisionOwnershipError,
        "Revision does not belong to this content item.",
    ),
)


def public_error_detail(error: Exception) -> str:
    """Return the fixed, client-safe message for a known application error."""
    for error_type, detail in _PUBLIC_DETAILS:
        if isinstance(error, error_type):
            return detail
    return DEFAULT_ERROR_DETAIL
