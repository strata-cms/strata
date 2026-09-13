from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

from strata_cms.application.content.search_indexing import reindex_from_event
from strata_cms.application.ports.content_delivery import (
    PublishedRevision,
)
from strata_cms.application.ports.content_types import PreparedContentData
from strata_cms.application.ports.messaging import MessageEnvelope
from strata_cms.application.ports.search import (
    SearchCapability,
    SearchDocument,
    SearchQuery,
    SearchResult,
)
from strata_cms.domain.revision import Revision, RevisionData
from strata_cms.domain.value_objects import (
    ActorId,
    ContentId,
    ContentTypeKey,
    RevisionId,
)

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
CONTENT_ID = ContentId(UUID(int=1))


class FakeQueries:
    def __init__(self, published: PublishedRevision | None) -> None:
        self._published = published

    def get_published(self, content_id: ContentId) -> PublishedRevision | None:
        del content_id
        return self._published

    def list_published(self, **kwargs: object) -> tuple[tuple[()], int]:
        del kwargs
        return (), 0


class FakeContentTypes:
    def prepare_for_write(
        self,
        *,
        type_key: ContentTypeKey,
        schema_version: int,
        data: Mapping[str, object],
    ) -> PreparedContentData:
        raise NotImplementedError

    def validate_revision(self, revision: Revision) -> None:
        del revision

    def delivery_data(self, revision: Revision) -> dict[str, object]:
        return revision.data.as_dict()


class FakeSearch:
    def __init__(self) -> None:
        self.indexed: list[SearchDocument] = []
        self.removed: list[UUID] = []

    @property
    def capabilities(self) -> frozenset[SearchCapability]:
        return frozenset()

    def index(self, document: SearchDocument) -> None:
        self.indexed.append(document)

    def remove(self, document_id: UUID) -> None:
        self.removed.append(document_id)

    def search(self, query: SearchQuery) -> SearchResult:
        del query
        return SearchResult(hits=(), total=0)


def _published_revision() -> PublishedRevision:
    return PublishedRevision(
        content_id=CONTENT_ID,
        type_key=ContentTypeKey("tests.article"),
        revision=Revision(
            id=RevisionId(uuid4()),
            content_id=CONTENT_ID,
            number=1,
            content_type=ContentTypeKey("tests.article"),
            schema_version=1,
            data=RevisionData.from_mapping({"title": "Bengal cats", "body": "Purr"}),
            created_at=NOW,
            created_by=ActorId("user:1"),
        ),
        published_at=NOW,
    )


def _event(event_type: str) -> MessageEnvelope:
    return MessageEnvelope(
        id=uuid4(),
        type=event_type,
        version=1,
        payload={"content_id": str(CONTENT_ID)},
        created_at=NOW,
    )


def test_published_event_indexes_flattened_text() -> None:
    search = FakeSearch()
    reindex_from_event(
        _event("strata.content.published"),
        queries=FakeQueries(_published_revision()),
        content_types=FakeContentTypes(),
        search=search,
    )

    assert len(search.indexed) == 1
    document = search.indexed[0]
    assert document.id == CONTENT_ID
    assert "Bengal cats" in document.text
    assert "Purr" in document.text
    assert document.fields["type"] == "tests.article"


def test_archived_event_removes_the_document() -> None:
    search = FakeSearch()
    reindex_from_event(
        _event("strata.content.archived"),
        queries=FakeQueries(_published_revision()),
        content_types=FakeContentTypes(),
        search=search,
    )

    assert search.removed == [CONTENT_ID]
    assert search.indexed == []


def test_restored_event_reindexes_when_still_published() -> None:
    search = FakeSearch()
    reindex_from_event(
        _event("strata.content.restored"),
        queries=FakeQueries(_published_revision()),
        content_types=FakeContentTypes(),
        search=search,
    )

    assert len(search.indexed) == 1


def test_restored_event_removes_when_not_published() -> None:
    search = FakeSearch()
    reindex_from_event(
        _event("strata.content.restored"),
        queries=FakeQueries(None),
        content_types=FakeContentTypes(),
        search=search,
    )

    assert search.removed == [CONTENT_ID]


def test_unrelated_event_type_is_ignored() -> None:
    search = FakeSearch()
    reindex_from_event(
        _event("strata.other.event"),
        queries=FakeQueries(_published_revision()),
        content_types=FakeContentTypes(),
        search=search,
    )

    assert search.indexed == []
    assert search.removed == []
