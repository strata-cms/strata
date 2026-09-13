"""Event publication port."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class IntegrationEvent:
    """Versioned fact published for decoupled integration consumers."""

    id: UUID
    type: str
    version: int
    payload: Mapping[str, object]
    occurred_at: datetime
    correlation_id: UUID | None = None
    causation_id: UUID | None = None


class EventPublisher(Protocol):
    """Persist/publish integration events without exposing broker details."""

    def publish(self, event: IntegrationEvent) -> None:
        """Publish an integration event with at-least-once semantics."""
        ...  # pragma: no cover - protocol declaration
