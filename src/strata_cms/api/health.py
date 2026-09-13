"""Public liveness endpoint."""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthResponseSerializer(serializers.Serializer[dict[str, str]]):
    """Schema for the public liveness response."""

    status = serializers.CharField(read_only=True)


class HealthView(APIView):
    """Return lightweight service liveness without touching domain state."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: HealthResponseSerializer})
    def get(self, request: Request) -> Response:
        """Return service liveness without disclosing internals."""
        del request
        return Response({"status": "ok"})
