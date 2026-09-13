"""Add a custom publish_contentrecord permission, separate from change."""

from django.db import migrations


class Migration(migrations.Migration):
    """Declare the publish permission via ContentRecord.Meta.permissions."""

    dependencies = [
        ("strata_persistence", "0003_outbox_dead_letter"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="contentrecord",
            options={
                "permissions": [
                    (
                        "publish_contentrecord",
                        "Can publish content (separate from editing drafts)",
                    )
                ]
            },
        ),
    ]
