"""Domain errors for content and revision invariants."""


class DomainError(Exception):
    """Base class for Strata domain errors."""


class InvalidContentTypeKeyError(DomainError, ValueError):
    """Raised when a persisted content type key is not namespaced/valid."""


class InvalidRevisionDataError(DomainError, ValueError):
    """Raised when revision data cannot be represented as strict JSON."""


class InvalidRevisionError(DomainError, ValueError):
    """Raised when revision metadata violates an invariant."""


class RevisionOwnershipError(DomainError, ValueError):
    """Raised when a revision does not belong to the target content item."""


class ConcurrentModificationError(DomainError, RuntimeError):
    """Raised when optimistic concurrency detects stale content state."""


class ContentArchivedError(DomainError, RuntimeError):
    """Raised when a mutation is attempted against archived content."""


class InvalidSlugError(DomainError, ValueError):
    """Raised when a route slug is not a valid URL path segment."""


class RouteCycleError(DomainError, ValueError):
    """Raised when a route move would make a node its own ancestor."""
