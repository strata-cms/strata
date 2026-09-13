"""Small validated value objects and strongly typed identifiers."""

import re
from dataclasses import dataclass
from typing import NewType
from uuid import UUID

from strata_cms.domain.errors import InvalidContentTypeKeyError

ContentId = NewType("ContentId", UUID)
RevisionId = NewType("RevisionId", UUID)
ActorId = NewType("ActorId", str)

_CONTENT_TYPE_KEY = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_MAX_KEY_LENGTH = 200


@dataclass(frozen=True, slots=True)
class ContentTypeKey:
    """Stable namespaced identifier such as ``strata.page``."""

    value: str

    def __post_init__(self) -> None:
        """Validate the stable persisted key."""
        if len(self.value) > _MAX_KEY_LENGTH or not _CONTENT_TYPE_KEY.fullmatch(
            self.value
        ):
            raise InvalidContentTypeKeyError(
                "Content type keys must be <= 200 chars and use lowercase "
                "namespaced identifiers such as 'acme_blog.article'."
            )

    def __str__(self) -> str:
        """Return the persisted string representation."""
        return self.value
