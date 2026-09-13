"""Django ORM persistence records; never use these as domain entities."""

import uuid

from django.db import models


class ContentRecord(models.Model):
    """Persistence representation of a stable content aggregate."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type_key = models.CharField(max_length=200, db_index=True)
    created_at = models.DateTimeField()
    created_by = models.CharField(max_length=255)
    latest_revision = models.ForeignKey(
        "RevisionRecord",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    latest_revision_number = models.PositiveBigIntegerField(default=0)
    published_revision = models.ForeignKey(
        "RevisionRecord",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.CharField(max_length=255, null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.CharField(max_length=255, null=True, blank=True)
    version = models.PositiveBigIntegerField(default=0)

    class Meta:
        """Persistence indexes and table naming."""

        db_table = "strata_content"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(latest_revision__isnull=True, latest_revision_number=0)
                    | models.Q(
                        latest_revision__isnull=False,
                        latest_revision_number__gt=0,
                    )
                ),
                name="strata_content_latest_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        published_revision__isnull=True,
                        published_at__isnull=True,
                        published_by__isnull=True,
                    )
                    | models.Q(
                        published_revision__isnull=False,
                        published_at__isnull=False,
                        published_by__isnull=False,
                    )
                ),
                name="strata_content_publish_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(archived_at__isnull=True, archived_by__isnull=True)
                    | models.Q(archived_at__isnull=False, archived_by__isnull=False)
                ),
                name="strata_content_archive_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["type_key", "id"], name="strata_content_type_id")
        ]
        permissions = [
            (
                "publish_contentrecord",
                "Can publish content (separate from editing drafts)",
            ),
        ]

    def __str__(self) -> str:
        """Return a concise persistence-record identity."""
        return f"{self.type_key}:{self.pk}"


class RevisionRecord(models.Model):
    """Persistence representation of an immutable content revision."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        ContentRecord,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    number = models.PositiveBigIntegerField()
    content_type_key = models.CharField(max_length=200)
    schema_version = models.PositiveIntegerField()
    data = models.JSONField()
    created_at = models.DateTimeField()
    created_by = models.CharField(max_length=255)

    class Meta:
        """Enforce stable per-content revision ordering."""

        db_table = "strata_revision"
        constraints = [
            models.UniqueConstraint(
                fields=["content", "number"],
                name="strata_revision_content_number_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["content", "-number"],
                name="strata_revision_content_num",
            )
        ]

    def __str__(self) -> str:
        """Return a concise persistence-record identity."""
        return f"{self.content_type_key}:{self.content_id}@{self.number}"


class OutboxMessageRecord(models.Model):
    """Durable integration event written in the authoritative transaction."""

    id = models.UUIDField(primary_key=True, editable=False)
    type = models.CharField(max_length=200, db_index=True)
    version = models.PositiveIntegerField()
    payload = models.JSONField()
    occurred_at = models.DateTimeField()
    correlation_id = models.UUIDField(null=True, blank=True)
    causation_id = models.UUIDField(null=True, blank=True)
    available_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    claimed_at = models.DateTimeField(null=True, blank=True)
    claimed_by = models.CharField(max_length=255, null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    dead_lettered_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        """Optimize worker scans while keeping the outbox provider-neutral."""

        db_table = "strata_outbox_message"
        indexes = [
            models.Index(
                fields=["processed_at", "dead_lettered_at", "available_at"],
                name="strata_outbox_pending",
            )
        ]

    def __str__(self) -> str:
        """Return a concise persistence-record identity."""
        return f"{self.type}:{self.pk}"


class SearchDocumentRecord(models.Model):
    """Rebuildable search projection of one published content item.

    Provider-neutral by construction: `text`/`fields` are the only data a
    `SearchBackend` adapter needs. Ranking/matching strategy lives in the
    adapter, not this schema.
    """

    id = models.UUIDField(primary_key=True, editable=False)
    text = models.TextField()
    fields = models.JSONField(default=dict)
    indexed_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Persistence table naming for the search projection."""

        db_table = "strata_search_document"

    def __str__(self) -> str:
        """Return a concise persistence-record identity."""
        return f"search:{self.pk}"


class ContentRouteRecord(models.Model):
    """Authoritative tree position: one content item's parent + slug.

    Optional: only content that explicitly attaches a route has a row here.
    Most content types are never routable and never appear in this table.
    """

    content = models.OneToOneField(
        ContentRecord,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="route",
    )
    parent = models.ForeignKey(
        ContentRecord,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="child_routes",
    )
    slug = models.CharField(max_length=200)
    version = models.PositiveBigIntegerField(default=0)

    class Meta:
        """Enforce sibling slug uniqueness, including at the tree root."""

        db_table = "strata_content_route"
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "slug"],
                condition=models.Q(parent__isnull=False),
                name="strata_route_unique_slug_per_parent",
            ),
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(parent__isnull=True),
                name="strata_route_unique_root_slug",
            ),
        ]
        indexes = [
            models.Index(fields=["parent"], name="strata_route_parent"),
        ]

    def __str__(self) -> str:
        """Return a concise persistence-record identity."""
        return f"route:{self.content_id}"


class RoutePathRecord(models.Model):
    """Rebuildable `path -> content` projection used by the Delivery API."""

    content = models.OneToOneField(
        ContentRecord,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="route_path",
    )
    path = models.CharField(max_length=2000, unique=True)

    class Meta:
        """Persistence table naming for the route path projection."""

        db_table = "strata_route_path"

    def __str__(self) -> str:
        """Return a concise persistence-record identity."""
        return f"path:{self.path}"
