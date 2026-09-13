"""Initial content, revision, and transactional outbox persistence schema."""

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    """Create the built-in Strata persistence records."""

    initial = True
    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.CreateModel(
            name="ContentRecord",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("type_key", models.CharField(db_index=True, max_length=200)),
                ("created_at", models.DateTimeField()),
                ("created_by", models.CharField(max_length=255)),
                (
                    "latest_revision_number",
                    models.PositiveBigIntegerField(default=0),
                ),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                (
                    "published_by",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("version", models.PositiveBigIntegerField(default=0)),
            ],
            options={"db_table": "strata_content"},
        ),
        migrations.CreateModel(
            name="OutboxMessageRecord",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("type", models.CharField(db_index=True, max_length=200)),
                ("version", models.PositiveIntegerField()),
                ("payload", models.JSONField()),
                ("occurred_at", models.DateTimeField()),
                ("correlation_id", models.UUIDField(blank=True, null=True)),
                ("causation_id", models.UUIDField(blank=True, null=True)),
                ("available_at", models.DateTimeField()),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("claimed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "claimed_by",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
            ],
            options={"db_table": "strata_outbox_message"},
        ),
        migrations.CreateModel(
            name="RevisionRecord",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("number", models.PositiveBigIntegerField()),
                ("content_type_key", models.CharField(max_length=200)),
                ("schema_version", models.PositiveIntegerField()),
                ("data", models.JSONField()),
                ("created_at", models.DateTimeField()),
                ("created_by", models.CharField(max_length=255)),
                (
                    "content",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="revisions",
                        to="strata_persistence.contentrecord",
                    ),
                ),
            ],
            options={"db_table": "strata_revision"},
        ),
        migrations.AddField(
            model_name="contentrecord",
            name="latest_revision",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="strata_persistence.revisionrecord",
            ),
        ),
        migrations.AddField(
            model_name="contentrecord",
            name="published_revision",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="strata_persistence.revisionrecord",
            ),
        ),
        migrations.AddConstraint(
            model_name="contentrecord",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(latest_revision__isnull=True, latest_revision_number=0)
                    | models.Q(
                        latest_revision__isnull=False,
                        latest_revision_number__gt=0,
                    )
                ),
                name="strata_content_latest_consistent",
            ),
        ),
        migrations.AddConstraint(
            model_name="contentrecord",
            constraint=models.CheckConstraint(
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
        ),
        migrations.AddConstraint(
            model_name="revisionrecord",
            constraint=models.UniqueConstraint(
                fields=("content", "number"),
                name="strata_revision_content_number_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="contentrecord",
            index=models.Index(
                fields=["type_key", "id"],
                name="strata_content_type_id",
            ),
        ),
        migrations.AddIndex(
            model_name="revisionrecord",
            index=models.Index(
                fields=["content", "-number"],
                name="strata_revision_content_num",
            ),
        ),
        migrations.AddIndex(
            model_name="outboxmessagerecord",
            index=models.Index(
                fields=["processed_at", "available_at"],
                name="strata_outbox_pending",
            ),
        ),
    ]
