from uuid import UUID

import pytest

from strata_cms.application.ports.search import SearchDocument, SearchQuery
from strata_cms.infrastructure.persistence.django.search import PostgresSearchBackend


@pytest.mark.django_db
def test_index_then_search_finds_matching_document() -> None:
    backend = PostgresSearchBackend()
    backend.index(
        SearchDocument(
            id=UUID(int=1),
            text="Bengal cats are wonderful companions",
            fields={"type": "tests.article"},
        )
    )

    result = backend.search(SearchQuery(text="Bengal"))

    assert result.total == 1
    assert result.hits[0].document_id == UUID(int=1)


@pytest.mark.django_db
def test_search_excludes_non_matching_documents() -> None:
    backend = PostgresSearchBackend()
    backend.index(SearchDocument(id=UUID(int=1), text="Bengal cats"))
    backend.index(SearchDocument(id=UUID(int=2), text="Siberian huskies"))

    result = backend.search(SearchQuery(text="huskies"))

    assert result.total == 1
    assert result.hits[0].document_id == UUID(int=2)


@pytest.mark.django_db
def test_search_filters_by_stored_fields() -> None:
    backend = PostgresSearchBackend()
    backend.index(
        SearchDocument(id=UUID(int=1), text="cats", fields={"type": "a.article"})
    )
    backend.index(
        SearchDocument(id=UUID(int=2), text="cats", fields={"type": "b.page"})
    )

    result = backend.search(SearchQuery(text="cats", filters={"type": "a.article"}))

    assert result.total == 1
    assert result.hits[0].document_id == UUID(int=1)


@pytest.mark.django_db
def test_reindexing_the_same_id_replaces_the_document() -> None:
    backend = PostgresSearchBackend()
    backend.index(SearchDocument(id=UUID(int=1), text="old text"))
    backend.index(SearchDocument(id=UUID(int=1), text="new text"))

    old = backend.search(SearchQuery(text="old"))
    new = backend.search(SearchQuery(text="new"))

    assert old.total == 0
    assert new.total == 1


@pytest.mark.django_db
def test_remove_deletes_the_document() -> None:
    backend = PostgresSearchBackend()
    backend.index(SearchDocument(id=UUID(int=1), text="removable"))

    backend.remove(UUID(int=1))

    result = backend.search(SearchQuery(text="removable"))
    assert result.total == 0


@pytest.mark.django_db
def test_removing_an_absent_document_is_a_no_op() -> None:
    backend = PostgresSearchBackend()

    backend.remove(UUID(int=404))


@pytest.mark.django_db
def test_search_respects_limit_and_offset() -> None:
    backend = PostgresSearchBackend()
    for i in range(5):
        backend.index(SearchDocument(id=UUID(int=i), text="paginated item"))

    page = backend.search(SearchQuery(text="paginated", limit=2, offset=2))

    assert page.total == 5
    assert len(page.hits) == 2


def test_baseline_backend_declares_no_optional_capabilities() -> None:
    backend = PostgresSearchBackend()

    assert backend.capabilities == frozenset()
