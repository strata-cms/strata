"""Durable message transport contracts."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MessageEnvelope:
    """Stable envelope for a versioned durable message."""

    id: UUID
    type: str
    version: int
    payload: Mapping[str, object]
    created_at: datetime
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    # Delivery attempts so far, including the current claim; 1 on first claim.
    attempts: int = 0


@dataclass(frozen=True, slots=True)
class MessageLease:
    """A claimed message that must be acknowledged, retried, or rejected."""

    message: MessageEnvelope
    lease_id: UUID


class DurableMessageQueue(Protocol):
    """At-least-once durable queue transport used by worker adapters."""

    def publish(
        self,
        message: MessageEnvelope,
        *,
        delay: timedelta | None = None,
    ) -> None:
        """Publish a message for eventual processing."""
        ...  # pragma: no cover - protocol declaration

    def claim(
        self,
        *,
        batch_size: int,
        visibility_timeout: timedelta,
    ) -> Sequence[MessageLease]:
        """Claim available messages for at-least-once processing."""
        ...  # pragma: no cover - protocol declaration

    def acknowledge(self, lease: MessageLease) -> None:
        """Mark a claimed message as successfully processed."""
        ...  # pragma: no cover - protocol declaration

    def retry(
        self,
        lease: MessageLease,
        *,
        delay: timedelta,
        reason: str,
    ) -> None:
        """Release a failed message for a later retry."""
        ...  # pragma: no cover - protocol declaration

    def reject(self, lease: MessageLease, *, reason: str) -> None:
        """Move a permanently failed message to terminal/dead-letter state."""
        ...  # pragma: no cover - protocol declaration
