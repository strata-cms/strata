"""Opt-in durable-queue worker: `python manage.py strata_worker`.

Runs independently of the web/API process against the same PostgreSQL-backed
outbox table. Safe to run as multiple concurrent processes/replicas: claiming
uses `SELECT ... FOR UPDATE SKIP LOCKED` so workers never contend for the same
row.
"""

import logging
import os
import signal
import socket
import time
from argparse import ArgumentParser
from datetime import timedelta
from types import FrameType
from typing import cast

from django.core.management.base import BaseCommand
from django.utils.module_loading import import_string

from strata_cms.infrastructure.persistence.django.outbox import DjangoOutboxQueue
from strata_cms.infrastructure.tasks.worker import (
    Dispatcher,
    exponential_backoff,
    log_only_dispatcher,
    run_worker_batch,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Claim, dispatch, and acknowledge/retry/dead-letter outbox messages."""

    help = __doc__

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Declare worker tuning flags; defaults suit light local usage."""
        parser.add_argument("--batch-size", type=int, default=20)
        parser.add_argument("--visibility-timeout", type=int, default=60)
        parser.add_argument("--max-attempts", type=int, default=5)
        parser.add_argument("--poll-interval", type=float, default=2.0)
        parser.add_argument(
            "--dispatcher",
            type=str,
            default=None,
            help="Dotted path to a callable(MessageEnvelope) -> None.",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process a single batch and exit instead of polling forever.",
        )

    def handle(self, *args: object, **options: object) -> None:
        """Poll the outbox until stopped, processing due messages in batches."""
        del args
        dispatcher_path = options["dispatcher"]
        dispatch: Dispatcher = (
            import_string(dispatcher_path)
            if isinstance(dispatcher_path, str)
            else log_only_dispatcher
        )
        queue = DjangoOutboxQueue(worker_id=f"{socket.gethostname()}:{os.getpid()}")
        visibility_timeout = timedelta(
            seconds=cast("int", options["visibility_timeout"])
        )
        poll_interval = cast("float", options["poll_interval"])
        batch_size = cast("int", options["batch_size"])
        max_attempts = cast("int", options["max_attempts"])
        run_once = cast("bool", options["once"])

        stop = _install_shutdown_handler()
        self.stdout.write("strata_worker started")
        while not stop.requested:
            processed = run_worker_batch(
                queue,
                dispatch=dispatch,
                batch_size=batch_size,
                visibility_timeout=visibility_timeout,
                max_attempts=max_attempts,
                backoff=exponential_backoff,
            )
            if run_once:
                break
            if processed == 0:
                time.sleep(poll_interval)
        self.stdout.write("strata_worker stopped")


class _ShutdownState:
    """Mutable flag flipped by signal handlers to end the poll loop cleanly."""

    def __init__(self) -> None:
        self.requested = False


def _install_shutdown_handler() -> _ShutdownState:
    state = _ShutdownState()

    def _handle(signum: int, frame: FrameType | None) -> None:
        del signum, frame
        state.requested = True

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)
    return state
