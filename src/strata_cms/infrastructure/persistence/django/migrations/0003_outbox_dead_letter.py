"""Add outbox dead-letter marker used by the durable-queue worker."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add dead_lettered_at to OutboxMessageRecord and refresh its scan index."""

    dependencies = [
        ("strata_persistence", "0002_content_archival"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="outboxmessagerecord",
            name="strata_outbox_pending",
        ),
        migrations.AddField(
            model_name="outboxmessagerecord",
            name="dead_lettered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="outboxmessagerecord",
            index=models.Index(
                fields=["processed_at", "dead_lettered_at", "available_at"],
                name="strata_outbox_pending",
            ),
        ),
    ]
