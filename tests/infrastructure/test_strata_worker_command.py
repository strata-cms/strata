import logging
from datetime import UTC, datetime
from uuid import UUID

import pytest
from django.core.management import call_command

from strata_cms.application.ports.events import IntegrationEvent
from strata_cms.infrastructure.persistence.django.models import OutboxMessageRecord
from strata_cms.infrastructure.persistence.django.outbox import (
    DjangoOutboxEventPublisher,
)


@pytest.mark.django_db
def test_strata_worker_once_drains_a_due_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    publisher = DjangoOutboxEventPublisher()
    publisher.publish(
        IntegrationEvent(
            id=UUID(int=1),
            type="tests.example",
            version=1,
            payload={},
            occurred_at=datetime(2026, 9, 13, 12, 0, tzinfo=UTC),
        )
    )

    with caplog.at_level(logging.INFO):
        call_command("strata_worker", "--once")

    record = OutboxMessageRecord.objects.get(pk=UUID(int=1))
    assert record.processed_at is not None
    assert "strata_worker dispatched message" in caplog.text
