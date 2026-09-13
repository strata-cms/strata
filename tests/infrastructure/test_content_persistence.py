from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

import pytest

from strata_cms.application.content.commands import CreateContent, PublishContent
from strata_cms.application.content.use_cases import create_content, publish_content
from strata_cms.application.ports.authorization import ContentAction, ContentActor
from strata_cms.application.ports.content_types import PreparedContentData
from strata_cms.domain.content import Content
from strata_cms.domain.errors import ConcurrentModificationError
from strata_cms.domain.revision import Revision, RevisionData
from strata_cms.domain.value_objects import ActorId, ContentId, ContentTypeKey
from strata_cms.infrastructure.persistence.django.models import (
    ContentRecord,
    OutboxMessageRecord,
    RevisionRecord,
)
from strata_cms.infrastructure.persistence.django.repositories import (
    DjangoContentRepository,
)
from strata_cms.infrastructure.persistence.django.unit_of_work import (
    DjangoContentUnitOfWork,
)

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)
ACTOR = ActorId("user:42")


class FrozenClock:
    def now(self) -> datetime:
        return NOW


class SequenceIds:
    def __init__(self, *values: int) -> None:
        self._values = iter(values)

    def new_uuid(self) -> UUID:
        return UUID(int=next(self._values))


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
ACTOR_CONTEXT = ContentActor(id=ACTOR, is_staff=True, permissions=frozenset())


class AllowAllPolicy:
    """Permissive fake policy: these tests exercise persistence, not authz."""

    def authorize(self, actor: ContentActor, action: ContentAction) -> None:
        del actor, action


POLICY = AllowAllPolicy()


@pytest.mark.django_db
def test_django_uow_round_trips_content_and_revision() -> None:
    result = create_content(
        CreateContent(
            type_key=ContentTypeKey("tests.article"),
            schema_version=1,
            data={"title": "Persisted"},
            actor_id=ACTOR,
        ),
        uow=DjangoContentUnitOfWork(),
        clock=FrozenClock(),
        ids=SequenceIds(1, 2),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    assert ContentRecord.objects.count() == 1
    assert RevisionRecord.objects.count() == 1

    with DjangoContentUnitOfWork() as uow:
        content = uow.contents.get(result.content_id)
        revision = uow.revisions.get(result.revision_id)
        uow.commit()

    assert content is not None
    assert revision is not None
    assert content.latest_revision_id == result.revision_id
    assert revision.data.as_dict() == {"title": "Persisted"}


@pytest.mark.django_db
def test_publish_writes_outbox_event_in_same_uow() -> None:
    created = create_content(
        CreateContent(
            type_key=ContentTypeKey("tests.article"),
            schema_version=1,
            data={"title": "Persisted"},
            actor_id=ACTOR,
        ),
        uow=DjangoContentUnitOfWork(),
        clock=FrozenClock(),
        ids=SequenceIds(1, 2),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    publish_content(
        PublishContent(
            content_id=created.content_id,
            revision_id=created.revision_id,
            expected_version=created.content_version,
            actor_id=ACTOR,
        ),
        uow=DjangoContentUnitOfWork(),
        clock=FrozenClock(),
        ids=SequenceIds(3),
        content_types=CONTENT_TYPES,
        policy=POLICY,
        actor=ACTOR_CONTEXT,
    )

    content = ContentRecord.objects.get(pk=created.content_id)
    message = OutboxMessageRecord.objects.get()
    assert content.published_revision_id == created.revision_id
    assert message.type == "strata.content.published"
    assert message.payload["content_id"] == str(created.content_id)


@pytest.mark.django_db
def test_uow_rolls_back_when_commit_is_not_called() -> None:
    content = Content(
        id=ContentId(UUID(int=1)),
        type_key=ContentTypeKey("tests.article"),
        created_at=NOW,
        created_by=ACTOR,
    )

    with DjangoContentUnitOfWork() as uow:
        uow.contents.add(content)

    assert ContentRecord.objects.count() == 0


@pytest.mark.django_db
def test_repository_compare_and_swap_rejects_stale_update() -> None:
    repository = DjangoContentRepository()
    content = Content(
        id=ContentId(UUID(int=1)),
        type_key=ContentTypeKey("tests.article"),
        created_at=NOW,
        created_by=ACTOR,
    )
    repository.add(content)

    with pytest.raises(ConcurrentModificationError):
        repository.update(content, expected_version=99)
