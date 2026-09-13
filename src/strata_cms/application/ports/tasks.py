"""Task execution port; task frameworks and brokers are separate concerns."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TaskRequest:
    """Versioned request for asynchronous work."""

    id: UUID
    type: str
    version: int
    payload: Mapping[str, object]
    correlation_id: UUID | None = None


class TaskQueue(Protocol):
    """Schedule work without coupling callers to Celery or a broker."""

    def enqueue(
        self,
        task: TaskRequest,
        *,
        delay: timedelta | None = None,
    ) -> None:
        """Schedule a task for eventual at-least-once execution."""
        ...  # pragma: no cover - protocol declaration
