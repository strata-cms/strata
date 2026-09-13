"""Transport-level gate for the privileged Management API.

Fine-grained per-action authorization lives in the shared
`ContentAuthorizationPolicy`, consulted by application use cases and by
read-only views alike, so Admin and API never drift into separate checks.
This class only rejects anonymous/non-staff callers early.
"""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class HasStrataManagementPermission(BasePermission):
    """Require an authenticated staff user; the policy decides the rest."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Reject anonymous or non-staff callers before any policy check."""
        del view
        user = request.user
        return bool(user.is_authenticated and user.is_staff)
