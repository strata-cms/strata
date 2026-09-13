"""Add content archival/restoration fields and consistency constraint."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add archived_at/archived_by fields to ContentRecord."""

    dependencies = [
        ("strata_persistence", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentrecord",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contentrecord",
            name="archived_by",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddConstraint(
            model_name="contentrecord",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("archived_at__isnull", True), ("archived_by__isnull", True)
                    ),
                    models.Q(
                        ("archived_at__isnull", False), ("archived_by__isnull", False)
                    ),
                    _connector="OR",
                ),
                name="strata_content_archive_consistent",
            ),
        ),
    ]
