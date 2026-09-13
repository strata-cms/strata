"""Add the content route tree and its rebuildable path projection."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Create ContentRouteRecord and RoutePathRecord."""

    dependencies = [
        ("strata_persistence", "0005_searchdocumentrecord"),
    ]

    operations = [
        migrations.CreateModel(
            name="RoutePathRecord",
            fields=[
                (
                    "content",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="route_path",
                        serialize=False,
                        to="strata_persistence.contentrecord",
                    ),
                ),
                ("path", models.CharField(max_length=2000, unique=True)),
            ],
            options={
                "db_table": "strata_route_path",
            },
        ),
        migrations.CreateModel(
            name="ContentRouteRecord",
            fields=[
                (
                    "content",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="route",
                        serialize=False,
                        to="strata_persistence.contentrecord",
                    ),
                ),
                ("slug", models.CharField(max_length=200)),
                ("version", models.PositiveBigIntegerField(default=0)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="child_routes",
                        to="strata_persistence.contentrecord",
                    ),
                ),
            ],
            options={
                "db_table": "strata_content_route",
                "indexes": [
                    models.Index(fields=["parent"], name="strata_route_parent"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("parent__isnull", False)),
                        fields=("parent", "slug"),
                        name="strata_route_unique_slug_per_parent",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("parent__isnull", True)),
                        fields=("slug",),
                        name="strata_route_unique_root_slug",
                    ),
                ],
            },
        ),
    ]
