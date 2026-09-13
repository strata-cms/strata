"""Unfold Admin adapter for schema-driven content editing."""

from dataclasses import asdict
from typing import TYPE_CHECKING
from uuid import UUID

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.urls.resolvers import URLPattern, URLResolver
from unfold.admin import ModelAdmin

from strata_cms.application.content.commands import ArchiveContent, RestoreContent
from strata_cms.application.content.use_cases import archive_content, restore_content
from strata_cms.application.errors import (
    ContentNotFoundError,
    ContentTypeUnavailableError,
    InvalidContentDataError,
    NotAuthorizedError,
)
from strata_cms.config.services import (
    get_clock,
    get_content_policy,
    get_content_queries,
    get_content_type_service,
    get_editor_catalog,
    get_id_generator,
    new_content_uow,
)
from strata_cms.domain.errors import (
    ConcurrentModificationError,
    InvalidContentTypeKeyError,
)
from strata_cms.domain.value_objects import ContentId, ContentTypeKey
from strata_cms.infrastructure.authorization.actor import build_content_actor
from strata_cms.infrastructure.persistence.django.models import ContentRecord

if TYPE_CHECKING:
    from django.db.models import QuerySet


@admin.register(ContentRecord)
class ContentRecordAdmin(ModelAdmin):
    """List persistence records but perform all writes through CMS use cases."""

    list_display = (
        "type_key",
        "id",
        "version",
        "latest_revision_number",
        "published_revision_id",
        "archived_at",
    )
    list_filter = ("type_key", "archived_at")
    search_fields = ("id", "type_key")
    ordering = ("type_key", "id")
    show_add_link = True
    actions = ("archive_selected", "restore_selected")

    @admin.action(description="Archive selected content")
    def archive_selected(
        self,
        request: HttpRequest,
        queryset: "QuerySet[ContentRecord]",
    ) -> None:
        """Archive each selected item through the application use case."""
        actor = build_content_actor(request.user)
        for record in queryset:
            try:
                archive_content(
                    ArchiveContent(
                        content_id=ContentId(record.id),
                        expected_version=record.version,
                        actor_id=actor.id,
                    ),
                    uow=new_content_uow(),
                    clock=get_clock(),
                    ids=get_id_generator(),
                    policy=get_content_policy(),
                    actor=actor,
                )
            except (
                ContentNotFoundError,
                ConcurrentModificationError,
                NotAuthorizedError,
            ) as exc:
                self.message_user(request, str(exc), level="error")

    @admin.action(description="Restore selected content")
    def restore_selected(
        self,
        request: HttpRequest,
        queryset: "QuerySet[ContentRecord]",
    ) -> None:
        """Restore each selected archived item through the application use case."""
        actor = build_content_actor(request.user)
        for record in queryset:
            try:
                restore_content(
                    RestoreContent(
                        content_id=ContentId(record.id),
                        expected_version=record.version,
                        actor_id=actor.id,
                    ),
                    uow=new_content_uow(),
                    clock=get_clock(),
                    ids=get_id_generator(),
                    policy=get_content_policy(),
                    actor=actor,
                )
            except (
                ContentNotFoundError,
                ConcurrentModificationError,
                NotAuthorizedError,
            ) as exc:
                self.message_user(request, str(exc), level="error")

    def get_urls(self) -> list[URLPattern | URLResolver]:
        """Add the schema-driven editor before Django's model change routes."""
        custom = [
            path(
                "<path:object_id>/editor/",
                self.admin_site.admin_view(self.editor_view),
                name="strata_persistence_contentrecord_editor",
            ),
        ]
        inherited: list[URLPattern | URLResolver] = super().get_urls()
        return custom + inherited

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: ContentRecord | None = None,
    ) -> bool:
        """Disable deletion until an explicit content deletion use case exists."""
        del request, obj
        return False

    def add_view(
        self,
        request: HttpRequest,
        form_url: str = "",
        extra_context: dict[str, object] | None = None,
    ) -> HttpResponse:
        """Render a type chooser or a new schema-driven working document."""
        del form_url
        if not self.has_add_permission(request):
            raise PermissionDenied
        type_value = request.GET.get("type")
        if not type_value:
            return self._render_type_chooser(request, extra_context=extra_context)

        try:
            type_key = ContentTypeKey(type_value)
        except InvalidContentTypeKeyError:
            return self._render_type_chooser(
                request,
                error="Invalid content type key.",
                extra_context=extra_context,
            )
        schema = get_editor_catalog().get_content_type(type_key)
        if schema is None or not schema.editable:
            return self._render_type_chooser(
                request,
                error=f"Content type '{type_key}' is not editable.",
                extra_context=extra_context,
            )
        return self._render_editor(
            request,
            schema=asdict(schema),
            document={
                "is_new": True,
                "type": str(type_key),
                "content_version": 0,
                "schema_version": schema.schema_version,
                "data": schema.initial_data,
                "revision_id": None,
                "published_revision_id": None,
            },
            extra_context=extra_context,
        )

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, object] | None = None,
    ) -> HttpResponse:
        """Never expose Django's persistence-record ModelForm as an editor."""
        del form_url, extra_context
        if not self.has_change_permission(request):
            raise PermissionDenied
        return redirect(
            "admin:strata_persistence_contentrecord_editor",
            object_id=object_id,
        )

    def editor_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        """Render the current immutable revision in the generic editor client."""
        if not self.has_change_permission(request):
            raise PermissionDenied
        try:
            content_id = ContentId(UUID(object_id))
        except ValueError:
            return self._render_type_chooser(request, error="Invalid content id.")
        document = get_content_queries().get_latest(content_id)
        if document is None:
            return self._render_type_chooser(request, error="Content was not found.")
        schema = get_editor_catalog().get_content_type(document.type_key)
        if schema is None or not schema.editable:
            return self._render_type_chooser(
                request,
                error=f"Content type '{document.type_key}' is not editable.",
            )
        try:
            prepared = get_content_type_service().prepare_for_write(
                type_key=document.type_key,
                schema_version=document.schema_version,
                data=document.data.as_dict(),
            )
        except (ContentTypeUnavailableError, InvalidContentDataError) as exc:
            return self._render_type_chooser(request, error=str(exc))
        return self._render_editor(
            request,
            schema=asdict(schema),
            document={
                "is_new": False,
                "content_id": str(document.content_id),
                "type": str(document.type_key),
                "content_version": document.content_version,
                "schema_version": prepared.schema_version,
                "data": prepared.data.as_dict(),
                "revision_id": str(document.revision_id),
                "revision_number": document.revision_number,
                "published_revision_id": (
                    str(document.published_revision_id)
                    if document.published_revision_id is not None
                    else None
                ),
                "is_archived": document.is_archived,
            },
        )

    def _render_type_chooser(
        self,
        request: HttpRequest,
        *,
        error: str = "",
        extra_context: dict[str, object] | None = None,
    ) -> TemplateResponse:
        editable = [
            asdict(item)
            for item in get_editor_catalog().list_content_types()
            if item.editable
        ]
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Choose content type",
            "content_types": editable,
            "error": error,
            **(extra_context or {}),
        }
        return TemplateResponse(
            request,
            "admin/strata/content_type_chooser.html",
            context,
        )

    def _render_editor(
        self,
        request: HttpRequest,
        *,
        schema: dict[str, object],
        document: dict[str, object],
        extra_context: dict[str, object] | None = None,
    ) -> TemplateResponse:
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": schema["label"],
            "editor_schema": schema,
            "editor_document": document,
            "editor_endpoints": {
                "create": reverse("api:management:content-create"),
                "revision": (
                    reverse(
                        "api:management:content-revision-create",
                        args=[document["content_id"]],
                    )
                    if not document["is_new"]
                    else None
                ),
                "publish": (
                    reverse(
                        "api:management:content-publish",
                        args=[document["content_id"]],
                    )
                    if not document["is_new"]
                    else None
                ),
                "history": (
                    reverse(
                        "api:management:content-revision-create",
                        args=[document["content_id"]],
                    )
                    if not document["is_new"]
                    else None
                ),
                "archive": (
                    reverse(
                        "api:management:content-archive",
                        args=[document["content_id"]],
                    )
                    if not document["is_new"]
                    else None
                ),
                "restore": (
                    reverse(
                        "api:management:content-restore",
                        args=[document["content_id"]],
                    )
                    if not document["is_new"]
                    else None
                ),
                "changelist": reverse(
                    "admin:strata_persistence_contentrecord_changelist"
                ),
            },
            **(extra_context or {}),
        }
        return TemplateResponse(
            request,
            "admin/strata/content_editor.html",
            context,
        )
