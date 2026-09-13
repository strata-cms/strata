"""Add the rebuildable search projection table."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Create SearchDocumentRecord."""

    dependencies = [
        ("strata_persistence", "0004_content_publish_permission"),
    ]

    operations = [
        migrations.CreateModel(
            name="SearchDocumentRecord",
            fields=[
                (
                    "id",
                    models.UUIDField(editable=False, primary_key=True, serialize=False),
                ),
                ("text", models.TextField()),
                ("fields", models.JSONField(default=dict)),
                ("indexed_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "strata_search_document",
            },
        ),
    ]
