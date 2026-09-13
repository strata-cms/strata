"""Stable application-facing ports implemented by infrastructure adapters."""

from strata_cms.application.ports.content_uow import ContentUnitOfWork
from strata_cms.application.ports.ids import IdGenerator

__all__ = ["ContentUnitOfWork", "IdGenerator"]
