from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from strata_cms.application.ports.messaging import MessageEnvelope
from strata_cms.infrastructure.persistence.django.models import OutboxMessageRecord
from strata_cms.infrastructure.persistence.django.outbox import DjangoOutboxQueue

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)


def _message(message_id: int) -> MessageEnvelope:
    return MessageEnvelope(
        id=UUID(int=message_id),
        type="tests.example",
        version=1,
        payload={"key": "value"},
        created_at=NOW,
    )


@pytest.mark.django_db
def test_publish_then_claim_returns_the_message_with_attempts_one() -> None:
    queue = DjangoOutboxQueue(worker_id="worker-1")
    queue.publish(_message(1))

    leases = queue.claim(batch_size=10, visibility_timeout=timedelta(seconds=60))

    assert len(leases) == 1
    assert leases[0].message.id == UUID(int=1)
    assert leases[0].message.attempts == 1


@pytest.mark.django_db
def test_claim_excludes_messages_not_yet_due() -> None:
    queue = DjangoOutboxQueue(worker_id="worker-1")
    queue.publish(_message(1), delay=timedelta(hours=1))

    leases = queue.claim(batch_size=10, visibility_timeout=timedelta(seconds=60))

    assert leases == []


@pytest.mark.django_db
def test_claim_excludes_messages_under_an_active_lease() -> None:
    queue = DjangoOutboxQueue(worker_id="worker-1")
    queue.publish(_message(1))
    queue.claim(batch_size=10, visibility_timeout=timedelta(seconds=60))

    leases = queue.claim(batch_size=10, visibility_timeout=timedelta(seconds=60))

    assert leases == []


@pytest.mark.django_db
def test_claim_recovers_messages_with_an_expired_lease() -> None:
    queue = DjangoOutboxQueue(worker_id="worker-1")
    queue.publish(_message(1))
    queue.claim(batch_size=10, visibility_timeout=timedelta(seconds=-1))

    leases = queue.claim(batch_size=10, visibility_timeout=timedelta(seconds=60))

    assert len(leases) == 1
    assert leases[0].message.attempts == 2


@pytest.mark.django_db
def test_acknowledge_marks_message_processed_and_unclaimable() -> None:
    queue = DjangoOutboxQueue(worker_id="worker-1")
    queue.publish(_message(1))
    [lease] = queue.claim(batch_size=10, visibility_timeout=timedelta(seconds=60))

    queue.acknowledge(lease)

    record = OutboxMessageRecord.objects.get(pk=UUID(int=1))
    assert record.processed_at is not None
    assert queue.claim(batch_size=10, visibility_timeout=timedelta(seconds=60)) == []


@pytest.mark.django_db
def test_retry_releases_claim_and_delays_availability() -> None:
    queue = DjangoOutboxQueue(worker_id="worker-1")
    queue.publish(_message(1))
    [lease] = queue.claim(batch_size=10, visibility_timeout=timedelta(seconds=60))

    queue.retry(lease, delay=timedelta(hours=1), reason="transient failure")

    record = OutboxMessageRecord.objects.get(pk=UUID(int=1))
    assert record.claimed_at is None
    assert record.claimed_by is None
    assert record.last_error == "transient failure"
    assert queue.claim(batch_size=10, visibility_timeout=timedelta(seconds=60)) == []


@pytest.mark.django_db
def test_reject_dead_letters_message_permanently() -> None:
    queue = DjangoOutboxQueue(worker_id="worker-1")
    queue.publish(_message(1))
    [lease] = queue.claim(batch_size=10, visibility_timeout=timedelta(seconds=60))

    queue.reject(lease, reason="permanent failure")

    record = OutboxMessageRecord.objects.get(pk=UUID(int=1))
    assert record.dead_lettered_at is not None
    assert record.last_error == "permanent failure"
    assert queue.claim(batch_size=10, visibility_timeout=timedelta(seconds=60)) == []


@pytest.mark.django_db
def test_claim_respects_batch_size() -> None:
    queue = DjangoOutboxQueue(worker_id="worker-1")
    for message_id in range(1, 6):
        queue.publish(_message(message_id))

    leases = queue.claim(batch_size=3, visibility_timeout=timedelta(seconds=60))

    assert len(leases) == 3
