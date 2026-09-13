"""Clock port for deterministic time-dependent application behavior."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Provide the current timezone-aware time."""

    def now(self) -> datetime:
        """Return the current timezone-aware timestamp."""
        ...  # pragma: no cover - protocol declaration
