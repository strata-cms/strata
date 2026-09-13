"""Transactional outbox: event publication and the durable worker queue."""

from collections.abc import Sequence
from datetime import timedelta
from uuid import UUID, uuid4

from django.db import transaction
from django.utils import timezone

from strata_cms.application.ports.events import IntegrationEvent
from strata_cms.application.ports.messaging import MessageEnvelope, MessageLease
from strata_cms.infrastructure.persistence.django.models import OutboxMessageRecord


class DjangoOutboxEventPublisher:
    """Persist integration events for later at-least-once delivery."""

    def __init__(self, *, using: str = "default") -> None:
        """Bind the adapter to a Django database alias."""
        self._using = using

    def publish(self, event: IntegrationEvent) -> None:
        """Insert an outbox record inside the caller-owned database transaction."""
        OutboxMessageRecord.objects.using(self._using).create(
            id=event.id,
            type=event.type,
            version=event.version,
            payload=dict(event.payload),
            occurred_at=event.occurred_at,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            available_at=event.occurred_at,
        )


def _envelope_from_record(record: OutboxMessageRecord) -> MessageEnvelope:
    """Rehydrate a durable-queue envelope from its persistence record."""
    return MessageEnvelope(
        id=record.id,
        type=record.type,
        version=record.version,
        payload=dict(record.payload),
        created_at=record.occurred_at,
        correlation_id=record.correlation_id,
        causation_id=record.causation_id,
        attempts=record.attempts,
    )


class DjangoOutboxQueue:
    """PostgreSQL-backed durable queue reusing the transactional outbox table.

    Implements the `DurableMessageQueue` port: safe multi-worker claiming via
    `SELECT ... FOR UPDATE SKIP LOCKED`, retry with caller-supplied backoff,
    visibility-timeout lease recovery (a claim's `available_at` is pushed
    forward and reverts automatically if never acknowledged/retried/rejected),
    and an explicit dead-letter terminal state.
    """

    def __init__(self, *, worker_id: str, using: str = "default") -> None:
        """Bind the adapter to a claimant identity and Django database alias."""
        self._worker_id = worker_id
        self._using = using

    def publish(
        self,
        message: MessageEnvelope,
        *,
        delay: timedelta | None = None,
    ) -> None:
        """Enqueue a message for eventual at-least-once processing."""
        available_at = timezone.now() + (delay or timedelta())
        OutboxMessageRecord.objects.using(self._using).create(
            id=message.id,
            type=message.type,
            version=message.version,
            payload=dict(message.payload),
            occurred_at=message.created_at,
            correlation_id=message.correlation_id,
            causation_id=message.causation_id,
            available_at=available_at,
        )

    def claim(
        self,
        *,
        batch_size: int,
        visibility_timeout: timedelta,
    ) -> Sequence[MessageLease]:
        """Claim a batch of due, unclaimed-or-lease-expired messages."""
        now = timezone.now()
        with transaction.atomic(using=self._using):
            records = list(
                OutboxMessageRecord.objects.using(self._using)
                .select_for_update(skip_locked=True)
                .filter(
                    processed_at__isnull=True,
                    dead_lettered_at__isnull=True,
                    available_at__lte=now,
                )
                .order_by("available_at")[:batch_size]
            )
            leases = []
            for record in records:
                record.claimed_at = now
                record.claimed_by = self._worker_id
                record.attempts += 1
                record.available_at = now + visibility_timeout
                record.save(
                    using=self._using,
                    update_fields=[
                        "claimed_at",
                        "claimed_by",
                        "attempts",
                        "available_at",
                    ],
                )
                leases.append(
                    MessageLease(
                        message=_envelope_from_record(record),
                        lease_id=uuid4(),
                    )
                )
        return leases

    def acknowledge(self, lease: MessageLease) -> None:
        """Mark a claimed message as successfully processed."""
        self._update(lease.message.id, processed_at=timezone.now())

    def retry(
        self,
        lease: MessageLease,
        *,
        delay: timedelta,
        reason: str,
    ) -> None:
        """Release a failed message for a later retry."""
        self._update(
            lease.message.id,
            available_at=timezone.now() + delay,
            last_error=reason,
            claimed_at=None,
            claimed_by=None,
        )

    def reject(self, lease: MessageLease, *, reason: str) -> None:
        """Move a permanently failed message to terminal dead-letter state."""
        self._update(
            lease.message.id,
            dead_lettered_at=timezone.now(),
            last_error=reason,
        )

    def _update(self, message_id: UUID, **fields: object) -> None:
        OutboxMessageRecord.objects.using(self._using).filter(pk=message_id).update(
            **fields
        )
