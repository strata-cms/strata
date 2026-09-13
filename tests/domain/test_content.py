from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import UUID

import pytest

from strata_cms.domain.content import Content
from strata_cms.domain.errors import (
    ConcurrentModificationError,
    ContentArchivedError,
    InvalidContentTypeKeyError,
    InvalidRevisionDataError,
    InvalidRevisionError,
    RevisionOwnershipError,
)
from strata_cms.domain.revision import RevisionData
from strata_cms.domain.value_objects import (
    ActorId,
    ContentId,
    ContentTypeKey,
    RevisionId,
)

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)
ACTOR = ActorId("user:42")


def _content(number: int = 1) -> Content:
    return Content(
        id=ContentId(UUID(int=number)),
        type_key=ContentTypeKey("tests.article"),
        created_at=NOW,
        created_by=ACTOR,
    )


def test_content_type_key_requires_namespace() -> None:
    with pytest.raises(InvalidContentTypeKeyError):
        ContentTypeKey("article")


def test_revision_data_is_an_immutable_copy() -> None:
    source: dict[str, object] = {"title": "Initial", "tags": ["one"]}
    data = RevisionData.from_mapping(source)

    source["title"] = "Changed"
    first_copy = data.as_dict()
    first_copy["title"] = "Also changed"

    assert data.as_dict() == {"tags": ["one"], "title": "Initial"}


def test_revision_data_rejects_non_json_values() -> None:
    with pytest.raises(InvalidRevisionDataError):
        RevisionData.from_mapping({"value": object()})


def test_create_revision_advances_draft_but_not_publication() -> None:
    content = _content()

    content, revision = content.create_revision(
        revision_id=RevisionId(UUID(int=10)),
        schema_version=1,
        data=RevisionData.from_mapping({"title": "Draft"}),
        actor_id=ACTOR,
        now=NOW,
    )

    assert revision.number == 1
    assert content.latest_revision_id == revision.id
    assert content.latest_revision_number == 1
    assert content.published_revision_id is None
    assert content.version == 1


def test_publish_points_at_revision_and_advances_version() -> None:
    content = _content()
    content, revision = content.create_revision(
        revision_id=RevisionId(UUID(int=10)),
        schema_version=1,
        data=RevisionData.from_mapping({"title": "Draft"}),
        actor_id=ACTOR,
        now=NOW,
    )

    content, changed = content.publish(revision, actor_id=ACTOR, now=NOW)

    assert changed is True
    assert content.published_revision_id == revision.id
    assert content.published_at == NOW
    assert content.published_by == ACTOR
    assert content.version == 2


def test_publish_rejects_revision_from_other_content() -> None:
    first = _content(1)
    second = _content(2)
    _, revision = first.create_revision(
        revision_id=RevisionId(UUID(int=10)),
        schema_version=1,
        data=RevisionData.from_mapping({}),
        actor_id=ACTOR,
        now=NOW,
    )

    with pytest.raises(RevisionOwnershipError):
        second.publish(revision, actor_id=ACTOR, now=NOW)


def test_require_version_rejects_stale_state() -> None:
    content = _content()

    with pytest.raises(ConcurrentModificationError):
        content.require_version(99)


def test_content_rejects_inconsistent_latest_revision_state() -> None:
    with pytest.raises(InvalidRevisionError):
        Content(
            id=ContentId(UUID(int=1)),
            type_key=ContentTypeKey("tests.article"),
            created_at=NOW,
            created_by=ACTOR,
            latest_revision_id=RevisionId(UUID(int=2)),
            latest_revision_number=0,
        )


def test_content_state_cannot_be_assigned_directly() -> None:
    content = _content()

    with pytest.raises(FrozenInstanceError):
        content.version = 99  # type: ignore[misc]


def test_archive_marks_content_and_advances_version() -> None:
    content = _content()

    content, changed = content.archive(actor_id=ACTOR, now=NOW)

    assert changed is True
    assert content.archived_at == NOW
    assert content.archived_by == ACTOR
    assert content.version == 1


def test_archiving_twice_is_idempotent() -> None:
    content = _content()
    content, _ = content.archive(actor_id=ACTOR, now=NOW)

    content, changed = content.archive(actor_id=ACTOR, now=NOW)

    assert changed is False
    assert content.version == 1


def test_restore_clears_archival_and_advances_version() -> None:
    content = _content()
    content, _ = content.archive(actor_id=ACTOR, now=NOW)

    content, changed = content.restore()

    assert changed is True
    assert content.archived_at is None
    assert content.archived_by is None
    assert content.version == 2


def test_restoring_non_archived_content_is_idempotent() -> None:
    content = _content()

    content, changed = content.restore()

    assert changed is False
    assert content.version == 0


def test_archived_content_rejects_new_revisions() -> None:
    content = _content()
    content, _ = content.archive(actor_id=ACTOR, now=NOW)

    with pytest.raises(ContentArchivedError):
        content.create_revision(
            revision_id=RevisionId(UUID(int=10)),
            schema_version=1,
            data=RevisionData.from_mapping({}),
            actor_id=ACTOR,
            now=NOW,
        )


def test_archived_content_rejects_publish() -> None:
    content = _content()
    content, revision = content.create_revision(
        revision_id=RevisionId(UUID(int=10)),
        schema_version=1,
        data=RevisionData.from_mapping({}),
        actor_id=ACTOR,
        now=NOW,
    )
    content, _ = content.archive(actor_id=ACTOR, now=NOW)

    with pytest.raises(ContentArchivedError):
        content.publish(revision, actor_id=ACTOR, now=NOW)


def test_content_rejects_inconsistent_archived_state() -> None:
    with pytest.raises(InvalidRevisionError):
        Content(
            id=ContentId(UUID(int=1)),
            type_key=ContentTypeKey("tests.article"),
            created_at=NOW,
            created_by=ACTOR,
            archived_at=NOW,
            archived_by=None,
        )
