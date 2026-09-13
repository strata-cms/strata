from uuid import UUID

import pytest

from strata_cms.domain.errors import InvalidSlugError
from strata_cms.domain.route import ContentRoute
from strata_cms.domain.value_objects import ContentId

CONTENT_ID = ContentId(UUID(int=1))
PARENT_ID = ContentId(UUID(int=2))


def test_valid_slug_is_accepted() -> None:
    route = ContentRoute(content_id=CONTENT_ID, parent_id=None, slug="about-us")

    assert route.slug == "about-us"
    assert route.version == 0


@pytest.mark.parametrize(
    "slug",
    [
        "",
        "About",
        "about_us",
        "-about",
        "about-",
        "about--us",
        "a" * 201,
    ],
)
def test_invalid_slug_shapes_are_rejected(slug: str) -> None:
    with pytest.raises(InvalidSlugError):
        ContentRoute(content_id=CONTENT_ID, parent_id=None, slug=slug)


def test_route_cannot_be_parented_to_itself() -> None:
    with pytest.raises(InvalidSlugError):
        ContentRoute(content_id=CONTENT_ID, parent_id=CONTENT_ID, slug="loop")


def test_moved_to_advances_version_and_updates_position() -> None:
    route = ContentRoute(content_id=CONTENT_ID, parent_id=None, slug="about")

    moved = route.moved_to(parent_id=PARENT_ID, slug="team")

    assert moved.parent_id == PARENT_ID
    assert moved.slug == "team"
    assert moved.version == 1
    assert route.version == 0
