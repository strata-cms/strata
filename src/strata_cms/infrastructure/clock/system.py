"""Default timezone-aware system clock adapter."""

from datetime import datetime

from django.utils import timezone


class DjangoClock:
    """Provide Django's timezone-aware current time."""

    def now(self) -> datetime:
        """Return the current timezone-aware timestamp."""
        return timezone.now()
