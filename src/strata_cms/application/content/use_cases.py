"""Content write use cases shared by HTTP, Admin, CLI, and workers."""

from strata_cms.application.content.commands import (
    ArchiveContent,
    CreateContent,
    CreateRevision,
    PublishContent,
    RestoreContent,
)
from strata_cms.application.content.results import (
    ContentLifecycleResult,
    ContentWriteResult,
)
from strata_cms.application.errors import ContentNotFoundError, RevisionNotFoundError
from strata_cms.application.ports.authorization import (
    ContentAction,
    ContentActor,
    ContentAuthorizationPolicy,
)
from strata_cms.application.ports.clock import Clock
from strata_cms.application.ports.content_types import ContentTypeService
from strata_cms.application.ports.content_uow import ContentUnitOfWork
from strata_cms.application.ports.events import IntegrationEvent
from strata_cms.application.ports.ids import IdGenerator
from strata_cms.domain.content import Content
from strata_cms.domain.value_objects import ContentId, RevisionId


def create_content(
    command: CreateContent,
    *,
    uow: ContentUnitOfWork,
    clock: Clock,
    ids: IdGenerator,
    content_types: ContentTypeService,
    policy: ContentAuthorizationPolicy,
    actor: ContentActor,
) -> ContentWriteResult:
    """Create a stable content identity and initial draft revision atomically."""
    policy.authorize(actor, ContentAction.CREATE)
    prepared = content_types.prepare_for_write(
        type_key=command.type_key,
        schema_version=command.schema_version,
        data=command.data,
    )
    now = clock.now()
    content = Content(
        id=ContentId(ids.new_uuid()),
        type_key=command.type_key,
        created_at=now,
        created_by=command.actor_id,
    )

    with uow:
        uow.contents.add(content)
        content, revision = content.create_revision(
            revision_id=RevisionId(ids.new_uuid()),
            schema_version=prepared.schema_version,
            data=prepared.data,
            actor_id=command.actor_id,
            now=now,
        )
        uow.revisions.add(revision)
        uow.contents.update(content, expected_version=0)
        uow.commit()

    return ContentWriteResult(
        content_id=content.id,
        revision_id=revision.id,
        content_version=content.version,
        revision_number=revision.number,
    )


def create_revision(
    command: CreateRevision,
    *,
    uow: ContentUnitOfWork,
    clock: Clock,
    ids: IdGenerator,
    content_types: ContentTypeService,
    policy: ContentAuthorizationPolicy,
    actor: ContentActor,
) -> ContentWriteResult:
    """Append an immutable draft revision without affecting public delivery."""
    policy.authorize(actor, ContentAction.CHANGE)
    with uow:
        content = uow.contents.get(command.content_id)
        if content is None:
            raise ContentNotFoundError(command.content_id)

        content.require_version(command.expected_version)
        prepared = content_types.prepare_for_write(
            type_key=content.type_key,
            schema_version=command.schema_version,
            data=command.data,
        )
        content, revision = content.create_revision(
            revision_id=RevisionId(ids.new_uuid()),
            schema_version=prepared.schema_version,
            data=prepared.data,
            actor_id=command.actor_id,
            now=clock.now(),
        )
        uow.revisions.add(revision)
        uow.contents.update(content, expected_version=command.expected_version)
        uow.commit()

    return ContentWriteResult(
        content_id=content.id,
        revision_id=revision.id,
        content_version=content.version,
        revision_number=revision.number,
    )


def publish_content(
    command: PublishContent,
    *,
    uow: ContentUnitOfWork,
    clock: Clock,
    ids: IdGenerator,
    content_types: ContentTypeService,
    policy: ContentAuthorizationPolicy,
    actor: ContentActor,
) -> ContentWriteResult:
    """Publish a revision and persist the integration event in the same UoW."""
    policy.authorize(actor, ContentAction.PUBLISH)
    with uow:
        content = uow.contents.get(command.content_id)
        if content is None:
            raise ContentNotFoundError(command.content_id)

        revision = uow.revisions.get(command.revision_id)
        if revision is None:
            raise RevisionNotFoundError(command.revision_id)

        content.require_version(command.expected_version)
        content_types.validate_revision(revision)
        now = clock.now()
        content, changed = content.publish(
            revision,
            actor_id=command.actor_id,
            now=now,
        )
        if changed:
            uow.contents.update(
                content,
                expected_version=command.expected_version,
            )
            uow.events.publish(
                IntegrationEvent(
                    id=ids.new_uuid(),
                    type="strata.content.published",
                    version=1,
                    payload={
                        "content_id": str(content.id),
                        "revision_id": str(revision.id),
                        "content_type": str(content.type_key),
                        "content_version": content.version,
                        "actor_id": str(command.actor_id),
                    },
                    occurred_at=now,
                )
            )
        uow.commit()

    return ContentWriteResult(
        content_id=content.id,
        revision_id=revision.id,
        content_version=content.version,
        revision_number=revision.number,
    )


def archive_content(
    command: ArchiveContent,
    *,
    uow: ContentUnitOfWork,
    clock: Clock,
    ids: IdGenerator,
    policy: ContentAuthorizationPolicy,
    actor: ContentActor,
) -> ContentLifecycleResult:
    """Archive content, blocking further edits/publishes until restored."""
    policy.authorize(actor, ContentAction.ARCHIVE)
    with uow:
        content = uow.contents.get(command.content_id)
        if content is None:
            raise ContentNotFoundError(command.content_id)

        content.require_version(command.expected_version)
        now = clock.now()
        content, changed = content.archive(actor_id=command.actor_id, now=now)
        if changed:
            uow.contents.update(content, expected_version=command.expected_version)
            uow.events.publish(
                IntegrationEvent(
                    id=ids.new_uuid(),
                    type="strata.content.archived",
                    version=1,
                    payload={
                        "content_id": str(content.id),
                        "content_type": str(content.type_key),
                        "content_version": content.version,
                        "actor_id": str(command.actor_id),
                    },
                    occurred_at=now,
                )
            )
        uow.commit()

    return ContentLifecycleResult(
        content_id=content.id,
        content_version=content.version,
        is_archived=True,
    )


def restore_content(
    command: RestoreContent,
    *,
    uow: ContentUnitOfWork,
    clock: Clock,
    ids: IdGenerator,
    policy: ContentAuthorizationPolicy,
    actor: ContentActor,
) -> ContentLifecycleResult:
    """Restore previously archived content to an editable/publishable state."""
    policy.authorize(actor, ContentAction.RESTORE)
    with uow:
        content = uow.contents.get(command.content_id)
        if content is None:
            raise ContentNotFoundError(command.content_id)

        content.require_version(command.expected_version)
        now = clock.now()
        content, changed = content.restore()
        if changed:
            uow.contents.update(content, expected_version=command.expected_version)
            uow.events.publish(
                IntegrationEvent(
                    id=ids.new_uuid(),
                    type="strata.content.restored",
                    version=1,
                    payload={
                        "content_id": str(content.id),
                        "content_type": str(content.type_key),
                        "content_version": content.version,
                        "actor_id": str(command.actor_id),
                    },
                    occurred_at=now,
                )
            )
        uow.commit()

    return ContentLifecycleResult(
        content_id=content.id,
        content_version=content.version,
        is_archived=False,
    )
