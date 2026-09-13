import copy
from collections.abc import Mapping
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

import pytest

from strata_cms.application.content.commands import (
    ArchiveContent,
    CreateContent,
    CreateRevision,
    PublishContent,
    RestoreContent,
)
from strata_cms.application.content.use_cases import (
    archive_content,
    create_content,
    create_revision,
    publish_content,
    restore_content,
)
from strata_cms.application.errors import ContentNotFoundError, RevisionNotFoundError
from strata_cms.application.ports.authorization import ContentAction, ContentActor
from strata_cms.application.ports.content_types import PreparedContentData
from strata_cms.application.ports.events import IntegrationEvent
from strata_cms.domain.content import Content
from strata_cms.domain.errors import ConcurrentModificationError, ContentArchivedError
from strata_cms.domain.revision import Revision, RevisionData
from strata_cms.domain.value_objects import (
    ActorId,
    ContentId,
    ContentTypeKey,
    RevisionId,
)

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)
ACTOR = ActorId("user:42")
ACTOR_CONTEXT = ContentActor(id=ACTOR, is_staff=True, permissions=frozenset())


class AllowAllPolicy:
    """Permissive fake policy: these tests exercise use-case behavior, not authz."""

    def authorize(self, actor: ContentActor, action: ContentAction) -> None:
        del actor, action


POLICY = AllowAllPolicy()


class FakeContentTypes:
    def prepare_for_write(
        self,
        *,
        type_key: ContentTypeKey,
        schema_version: int,
        data: Mapping[str, object],
    ) -> PreparedContentData:
        del type_key
        return PreparedContentData(
            schema_version=schema_version,
            data=RevisionData.from_mapping(data),
        )

    def validate_revision(self, revision: Revision) -> None:
        del revision

    def delivery_data(self, revision: Revision) -> dict[str, object]:
        return revision.data.as_dict()


CONTENT_TYPES = FakeContentTypes()


class FrozenClock:
    def now(self) -> datetime:
        return NOW


class SequenceIds:
    def __init__(self, *values: int) -> None:
        self._values = iter(values)

    def new_uuid(self) -> UUID:
        return UUID(int=next(self._values))


class FakeContentRepository:
    def __init__(self) -> None:
        self.items: dict[ContentId, Content] = {}

    def get(self, content_id: ContentId) -> Content | None:
        item = self.items.get(content_id)
        return copy.deepcopy(item) if item is not None else None

    def add(self, content: Content) -> None:
        self.items[content.id] = copy.deepcopy(content)

    def update(self, content: Content, *, expected_version: int) -> None:
        persisted = self.items.get(content.id)
        if persisted is None or persisted.version != expected_version:
            raise ConcurrentModificationError("stale fake aggregate")
        self.items[content.id] = copy.deepcopy(content)


class FakeRevisionRepository:
    def __init__(self) -> None:
        self.items: dict[RevisionId, Revision] = {}

    def get(self, revision_id: RevisionId) -> Revision | None:
        return self.items.get(revision_id)

    def add(self, revision: Revision) -> None:
        self.items[revision.id] = revision


class FakeEvents:
    def __init__(self) -> None:
        self.items: list[IntegrationEvent] = []

    def publish(self, event: IntegrationEvent) -> None:
        self.items.append(event)


class FakeContentUnitOfWork:
    def __init__(self) -> None:
        self.contents = FakeContentRepository()
        self.revisions = FakeRevisionRepository()
        self.events = FakeEvents()
        self.committed = False

    def __enter__(self) -> "FakeContentUnitOfWork":
        self.committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.committed = False


def test_create_content_persists_identity_and_initial_revision() -> None:
    uow = FakeContentUnitOfWork()

    result = create_content(
        CreateContent(
            type_key=ContentTypeKey("tests.article"),
            schema_version=1,
            data={"title": "First"},
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(1, 2),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    persisted = uow.contents.get(result.content_id)
    revision = uow.revisions.get(result.revision_id)
    assert persisted is not None
    assert revision is not None
    assert persisted.latest_revision_id == result.revision_id
    assert persisted.published_revision_id is None
    assert result.content_version == 1
    assert result.revision_number == 1
    assert uow.committed is True


def test_create_revision_preserves_published_pointer() -> None:
    uow = FakeContentUnitOfWork()
    created = create_content(
        CreateContent(
            type_key=ContentTypeKey("tests.article"),
            schema_version=1,
            data={"title": "First"},
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(1, 2),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    second = create_revision(
        CreateRevision(
            content_id=created.content_id,
            expected_version=created.content_version,
            schema_version=2,
            data={"title": "Second"},
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(3),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    persisted = uow.contents.get(created.content_id)
    assert persisted is not None
    assert persisted.latest_revision_id == second.revision_id
    assert persisted.published_revision_id is None
    assert second.revision_number == 2
    assert second.content_version == 2


def test_create_revision_rejects_stale_content_version() -> None:
    uow = FakeContentUnitOfWork()
    created = create_content(
        CreateContent(
            type_key=ContentTypeKey("tests.article"),
            schema_version=1,
            data={},
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(1, 2),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    with pytest.raises(ConcurrentModificationError):
        create_revision(
            CreateRevision(
                content_id=created.content_id,
                expected_version=0,
                schema_version=1,
                data={},
                actor_id=ACTOR,
            ),
            uow=uow,
            clock=FrozenClock(),
            ids=SequenceIds(3),
            content_types=CONTENT_TYPES,
            policy=POLICY,
            actor=ACTOR_CONTEXT,
        )


def test_publish_updates_pointer_and_writes_integration_event() -> None:
    uow = FakeContentUnitOfWork()
    created = create_content(
        CreateContent(
            type_key=ContentTypeKey("tests.article"),
            schema_version=1,
            data={"title": "First"},
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(1, 2),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    published = publish_content(
        PublishContent(
            content_id=created.content_id,
            revision_id=created.revision_id,
            expected_version=created.content_version,
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(3),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    persisted = uow.contents.get(created.content_id)
    assert persisted is not None
    assert persisted.published_revision_id == created.revision_id
    assert published.content_version == 2
    assert len(uow.events.items) == 1
    event = uow.events.items[0]
    assert event.type == "strata.content.published"
    assert event.payload["revision_id"] == str(created.revision_id)


def test_create_revision_rejects_missing_content() -> None:
    uow = FakeContentUnitOfWork()

    with pytest.raises(ContentNotFoundError):
        create_revision(
            CreateRevision(
                content_id=ContentId(UUID(int=404)),
                expected_version=0,
                schema_version=1,
                data={},
                actor_id=ACTOR,
            ),
            uow=uow,
            clock=FrozenClock(),
            ids=SequenceIds(1),
            content_types=CONTENT_TYPES,
            policy=POLICY,
            actor=ACTOR_CONTEXT,
        )


def test_publish_rejects_missing_revision() -> None:
    uow = FakeContentUnitOfWork()
    created = create_content(
        CreateContent(
            type_key=ContentTypeKey("tests.article"),
            schema_version=1,
            data={},
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(1, 2),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    with pytest.raises(RevisionNotFoundError):
        publish_content(
            PublishContent(
                content_id=created.content_id,
                revision_id=RevisionId(UUID(int=404)),
                expected_version=created.content_version,
                actor_id=ACTOR,
            ),
            uow=uow,
            clock=FrozenClock(),
            ids=SequenceIds(3),
            content_types=CONTENT_TYPES,
            policy=POLICY,
            actor=ACTOR_CONTEXT,
        )


def test_republishing_same_revision_does_not_emit_duplicate_event() -> None:
    uow = FakeContentUnitOfWork()
    created = create_content(
        CreateContent(
            type_key=ContentTypeKey("tests.article"),
            schema_version=1,
            data={},
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(1, 2),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )
    first = publish_content(
        PublishContent(
            content_id=created.content_id,
            revision_id=created.revision_id,
            expected_version=created.content_version,
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(3),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    second = publish_content(
        PublishContent(
            content_id=created.content_id,
            revision_id=created.revision_id,
            expected_version=first.content_version,
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(4),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    assert second.content_version == first.content_version
    assert len(uow.events.items) == 1


def test_create_content_persists_content_type_normalized_snapshot() -> None:
    class NormalizingContentTypes(FakeContentTypes):
        def prepare_for_write(
            self,
            *,
            type_key: ContentTypeKey,
            schema_version: int,
            data: Mapping[str, object],
        ) -> PreparedContentData:
            del type_key, schema_version, data
            return PreparedContentData(
                schema_version=7,
                data=RevisionData.from_mapping({"normalized": True}),
            )

    uow = FakeContentUnitOfWork()
    result = create_content(
        CreateContent(
            type_key=ContentTypeKey("tests.article"),
            schema_version=1,
            data={"legacy": "value"},
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(10, 11),
        content_types=NormalizingContentTypes(),
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    revision = uow.revisions.get(result.revision_id)
    assert revision is not None
    assert revision.schema_version == 7
    assert revision.data.as_dict() == {"normalized": True}


def test_archive_content_blocks_further_edits_and_publishes() -> None:
    uow = FakeContentUnitOfWork()
    created = create_content(
        CreateContent(
            type_key=ContentTypeKey("tests.article"),
            schema_version=1,
            data={"title": "First"},
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(1, 2),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    archived = archive_content(
        ArchiveContent(
            content_id=created.content_id,
            expected_version=created.content_version,
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(3),
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    assert archived.is_archived is True
    assert archived.content_version == 2
    assert len(uow.events.items) == 1
    assert uow.events.items[0].type == "strata.content.archived"

    with pytest.raises(ContentArchivedError):
        create_revision(
            CreateRevision(
                content_id=created.content_id,
                expected_version=archived.content_version,
                schema_version=1,
                data={"title": "Edit while archived"},
                actor_id=ACTOR,
            ),
            uow=uow,
            clock=FrozenClock(),
            ids=SequenceIds(4),
            content_types=CONTENT_TYPES,
            policy=POLICY,
            actor=ACTOR_CONTEXT,
        )

    with pytest.raises(ContentArchivedError):
        publish_content(
            PublishContent(
                content_id=created.content_id,
                revision_id=created.revision_id,
                expected_version=archived.content_version,
                actor_id=ACTOR,
            ),
            uow=uow,
            clock=FrozenClock(),
            ids=SequenceIds(5),
            content_types=CONTENT_TYPES,
            policy=POLICY,
            actor=ACTOR_CONTEXT,
        )


def test_archiving_twice_does_not_emit_duplicate_event() -> None:
    uow = FakeContentUnitOfWork()
    created = create_content(
        CreateContent(
            type_key=ContentTypeKey("tests.article"),
            schema_version=1,
            data={},
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(1, 2),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )
    first = archive_content(
        ArchiveContent(
            content_id=created.content_id,
            expected_version=created.content_version,
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(3),
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    second = archive_content(
        ArchiveContent(
            content_id=created.content_id,
            expected_version=first.content_version,
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(4),
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    assert second.content_version == first.content_version
    assert len(uow.events.items) == 1


def test_restore_content_allows_edits_again() -> None:
    uow = FakeContentUnitOfWork()
    created = create_content(
        CreateContent(
            type_key=ContentTypeKey("tests.article"),
            schema_version=1,
            data={"title": "First"},
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(1, 2),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )
    archived = archive_content(
        ArchiveContent(
            content_id=created.content_id,
            expected_version=created.content_version,
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(3),
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    restored = restore_content(
        RestoreContent(
            content_id=created.content_id,
            expected_version=archived.content_version,
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(4),
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    assert restored.is_archived is False
    revised = create_revision(
        CreateRevision(
            content_id=created.content_id,
            expected_version=restored.content_version,
            schema_version=1,
            data={"title": "Edit after restore"},
            actor_id=ACTOR,
        ),
        uow=uow,
        clock=FrozenClock(),
        ids=SequenceIds(5),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )
    assert revised.revision_number == 2


def test_archive_rejects_missing_content() -> None:
    uow = FakeContentUnitOfWork()

    with pytest.raises(ContentNotFoundError):
        archive_content(
            ArchiveContent(
                content_id=ContentId(UUID(int=404)),
                expected_version=0,
                actor_id=ACTOR,
            ),
            uow=uow,
            clock=FrozenClock(),
            ids=SequenceIds(1),
            policy=POLICY,
            actor=ACTOR_CONTEXT,
        )
