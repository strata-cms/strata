"""Generic durable-queue worker loop: claim, dispatch, ack/retry/dead-letter.

Framework-agnostic aside from the `DurableMessageQueue` port it depends on, so
it works unchanged against the Django-backed outbox queue or any external
adapter (Celery/RabbitMQ/etc.) implementing the same port.
"""

import logging
from collections.abc import Callable
from datetime import timedelta

from strata_cms.application.ports.messaging import DurableMessageQueue, MessageEnvelope

logger = logging.getLogger(__name__)

Dispatcher = Callable[[MessageEnvelope], None]
BackoffPolicy = Callable[[int], timedelta]


def log_only_dispatcher(message: MessageEnvelope) -> None:
    """Default dispatcher: observe and acknowledge without side effects.

    Concrete integrations (webhooks, search indexing, etc.) plug in their own
    dispatcher; this keeps the built-in worker operable and lossless before
    any such consumer exists.
    """
    logger.info(
        "strata_worker dispatched message id=%s type=%s version=%d attempts=%d",
        message.id,
        message.type,
        message.version,
        message.attempts,
    )


def exponential_backoff(attempts: int) -> timedelta:
    """Return a capped exponential retry delay based on attempts so far."""
    seconds = min(2**attempts, 300)
    return timedelta(seconds=seconds)


def run_worker_batch(
    queue: DurableMessageQueue,
    *,
    dispatch: Dispatcher = log_only_dispatcher,
    batch_size: int = 20,
    visibility_timeout: timedelta = timedelta(seconds=60),
    max_attempts: int = 5,
    backoff: BackoffPolicy = exponential_backoff,
) -> int:
    """Claim and process one batch; return the number of messages claimed."""
    leases = queue.claim(batch_size=batch_size, visibility_timeout=visibility_timeout)
    for lease in leases:
        try:
            dispatch(lease.message)
        except Exception as exc:
            if lease.message.attempts >= max_attempts:
                logger.error(
                    "strata_worker dead-lettered message id=%s type=%s "
                    "after %d attempts: %s",
                    lease.message.id,
                    lease.message.type,
                    lease.message.attempts,
                    exc,
                )
                queue.reject(lease, reason=str(exc))
            else:
                logger.warning(
                    "strata_worker retrying message id=%s type=%s attempt %d: %s",
                    lease.message.id,
                    lease.message.type,
                    lease.message.attempts,
                    exc,
                )
                queue.retry(
                    lease,
                    delay=backoff(lease.message.attempts),
                    reason=str(exc),
                )
        else:
            queue.acknowledge(lease)
    return len(leases)
