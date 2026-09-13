"""Query-parameter validation for the public Delivery API."""

from typing import Any

from rest_framework import serializers

MAX_LIST_LIMIT = 100
DEFAULT_LIST_LIMIT = 20


class ContentListQuerySerializer(serializers.Serializer[Any]):
    """Validate optional type filter plus limit/offset pagination."""

    type = serializers.CharField(max_length=200, required=False, allow_blank=False)
    limit = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=MAX_LIST_LIMIT,
        default=DEFAULT_LIST_LIMIT,
    )
    offset = serializers.IntegerField(required=False, min_value=0, default=0)


class ContentSearchQuerySerializer(serializers.Serializer[Any]):
    """Validate a search query string plus optional type filter/pagination."""

    q = serializers.CharField(max_length=500, allow_blank=False)
    type = serializers.CharField(max_length=200, required=False, allow_blank=False)
    limit = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=MAX_LIST_LIMIT,
        default=DEFAULT_LIST_LIMIT,
    )
    offset = serializers.IntegerField(required=False, min_value=0, default=0)
