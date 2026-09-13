from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from strata_cms.application.ports.messaging import MessageEnvelope, MessageLease
from strata_cms.infrastructure.tasks.worker import run_worker_batch

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)


def _envelope(message_id: int, *, attempts: int = 1) -> MessageEnvelope:
    return MessageEnvelope(
        id=UUID(int=message_id),
        type="tests.example",
        version=1,
        payload={},
        created_at=NOW,
        attempts=attempts,
    )


class FakeQueue:
    def __init__(self, leases: Sequence[MessageLease]) -> None:
        self._leases = list(leases)
        self.acknowledged: list[MessageLease] = []
        self.retried: list[tuple[MessageLease, timedelta, str]] = []
        self.rejected: list[tuple[MessageLease, str]] = []

    def publish(
        self, message: MessageEnvelope, *, delay: timedelta | None = None
    ) -> None:
        raise NotImplementedError

    def claim(
        self, *, batch_size: int, visibility_timeout: timedelta
    ) -> Sequence[MessageLease]:
        del batch_size, visibility_timeout
        leases, self._leases = self._leases, []
        return leases

    def acknowledge(self, lease: MessageLease) -> None:
        self.acknowledged.append(lease)

    def retry(self, lease: MessageLease, *, delay: timedelta, reason: str) -> None:
        self.retried.append((lease, delay, reason))

    def reject(self, lease: MessageLease, *, reason: str) -> None:
        self.rejected.append((lease, reason))


def test_successful_dispatch_acknowledges_message() -> None:
    lease = MessageLease(message=_envelope(1), lease_id=UUID(int=100))
    queue = FakeQueue([lease])

    processed = run_worker_batch(queue, dispatch=lambda _message: None)

    assert processed == 1
    assert queue.acknowledged == [lease]
    assert queue.retried == []
    assert queue.rejected == []


def test_failed_dispatch_below_max_attempts_retries_with_backoff() -> None:
    lease = MessageLease(message=_envelope(1, attempts=2), lease_id=UUID(int=100))
    queue = FakeQueue([lease])

    def failing_dispatch(_message: MessageEnvelope) -> None:
        raise RuntimeError("boom")

    run_worker_batch(
        queue,
        dispatch=failing_dispatch,
        max_attempts=5,
        backoff=lambda attempts: timedelta(seconds=attempts * 10),
    )

    assert queue.acknowledged == []
    assert len(queue.retried) == 1
    retried_lease, delay, reason = queue.retried[0]
    assert retried_lease is lease
    assert delay == timedelta(seconds=20)
    assert reason == "boom"
    assert queue.rejected == []


def test_failed_dispatch_at_max_attempts_dead_letters_message() -> None:
    lease = MessageLease(message=_envelope(1, attempts=5), lease_id=UUID(int=100))
    queue = FakeQueue([lease])

    def failing_dispatch(_message: MessageEnvelope) -> None:
        raise RuntimeError("permanent failure")

    run_worker_batch(queue, dispatch=failing_dispatch, max_attempts=5)

    assert queue.acknowledged == []
    assert queue.retried == []
    assert len(queue.rejected) == 1
    rejected_lease, reason = queue.rejected[0]
    assert rejected_lease is lease
    assert reason == "permanent failure"


def test_one_failing_message_does_not_block_the_rest_of_the_batch() -> None:
    ok_lease = MessageLease(message=_envelope(1), lease_id=UUID(int=100))
    bad_lease = MessageLease(message=_envelope(2), lease_id=UUID(int=101))
    queue = FakeQueue([bad_lease, ok_lease])

    def dispatch(message: MessageEnvelope) -> None:
        if message.id == bad_lease.message.id:
            raise RuntimeError("boom")

    processed = run_worker_batch(queue, dispatch=dispatch, max_attempts=5)

    assert processed == 2
    assert queue.acknowledged == [ok_lease]
    assert len(queue.retried) == 1
    assert queue.retried[0][0] is bad_lease
