"""Baseline search backend: PostgreSQL full-text search over a projection table.

Falls back to a plain substring match on non-PostgreSQL databases (SQLite is
used for lightweight local/test runs); production search semantics are
defined against PostgreSQL, matching the durable-queue precedent.
"""

from uuid import UUID

from django.contrib.postgres.search import (
    SearchQuery as PgSearchQuery,
)
from django.contrib.postgres.search import (
    SearchRank,
    SearchVector,
)
from django.db import connection

from strata_cms.application.ports.search import (
    SearchCapability,
    SearchDocument,
    SearchHit,
    SearchQuery,
    SearchResult,
)
from strata_cms.infrastructure.persistence.django.models import SearchDocumentRecord


class PostgresSearchBackend:
    """Index/query the rebuildable `SearchDocumentRecord` projection."""

    def __init__(self, *, using: str = "default") -> None:
        """Bind the adapter to a Django database alias."""
        self._using = using

    @property
    def capabilities(self) -> frozenset[SearchCapability]:
        """Return the (empty) set of optional capabilities this baseline supports."""
        return frozenset()

    def index(self, document: SearchDocument) -> None:
        """Insert or replace a searchable document."""
        SearchDocumentRecord.objects.using(self._using).update_or_create(
            id=document.id,
            defaults={"text": document.text, "fields": dict(document.fields)},
        )

    def remove(self, document_id: UUID) -> None:
        """Remove a searchable document if present."""
        SearchDocumentRecord.objects.using(self._using).filter(pk=document_id).delete()

    def search(self, query: SearchQuery) -> SearchResult:
        """Execute a baseline search query, ranked when running on PostgreSQL."""
        queryset = SearchDocumentRecord.objects.using(self._using).all()
        for key, value in query.filters.items():
            queryset = queryset.filter(**{f"fields__{key}": value})

        if connection.vendor == "postgresql":
            vector = SearchVector("text")
            pg_query = PgSearchQuery(query.text)
            queryset = (
                queryset.annotate(rank=SearchRank(vector, pg_query))
                .filter(rank__gt=0)
                .order_by("-rank")
            )
        else:
            queryset = queryset.filter(text__icontains=query.text).order_by(
                "-indexed_at"
            )

        total = queryset.count()
        page = queryset[query.offset : query.offset + query.limit]
        hits = tuple(
            SearchHit(
                document_id=record.id,
                score=getattr(record, "rank", None),
                fields=record.fields,
            )
            for record in page
        )
        return SearchResult(hits=hits, total=total)
