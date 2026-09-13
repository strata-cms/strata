"""Application content-type adapter backed by the immutable Strata registry."""

from collections.abc import Mapping

from strata_cms.application.errors import (
    ContentDataProblem,
    ContentTypeUnavailableError,
    InvalidContentDataError,
)
from strata_cms.application.ports.content_types import (
    ContentTypeService,
    PreparedContentData,
)
from strata_cms.domain.errors import InvalidRevisionDataError
from strata_cms.domain.revision import Revision, RevisionData
from strata_cms.domain.value_objects import ContentTypeKey
from strata_cms.plugin_api.errors import (
    BlockValidationError,
    ContentTypeNotFoundError,
    ContentValidationError,
    SchemaError,
)
from strata_cms.plugin_api.registry import RegisteredContentTypeEntry, StrataRegistry


class RegistryContentTypeService(ContentTypeService):
    """Bridge registry schemas and structured blocks into application use cases."""

    def __init__(self, registry: StrataRegistry) -> None:
        """Bind the adapter to one frozen plugin registry."""
        self._registry = registry

    def prepare_for_write(
        self,
        *,
        type_key: ContentTypeKey,
        schema_version: int,
        data: Mapping[str, object],
    ) -> PreparedContentData:
        """Normalize historical input and embedded blocks to canonical schemas."""
        entry = self._require(type_key)
        try:
            _normalized, value = self._normalize_and_decode(
                entry,
                schema_version=schema_version,
                data=RevisionData.from_mapping(data),
            )
            encoded = entry.definition.encode_untyped(value)
            canonical = self._registry.blocks.normalize_content_fields(
                encoded.data,
                entry.definition.block_fields,
            )
        except (InvalidRevisionDataError, SchemaError) as exc:
            raise self._invalid_data(type_key, exc) from exc

        return PreparedContentData(
            schema_version=encoded.schema_version,
            data=canonical,
        )

    def validate_revision(self, revision: Revision) -> None:
        """Require installed schema/block support and semantic validity."""
        entry = self._require(revision.content_type)
        try:
            self._normalize_and_decode(
                entry,
                schema_version=revision.schema_version,
                data=revision.data,
            )
        except (InvalidRevisionDataError, SchemaError) as exc:
            raise self._invalid_data(revision.content_type, exc) from exc

    def delivery_data(self, revision: Revision) -> dict[str, object]:
        """Decode a snapshot and render nested blocks for the Delivery API."""
        entry = self._require(revision.content_type)
        try:
            normalized, _value = self._normalize_and_decode(
                entry,
                schema_version=revision.schema_version,
                data=revision.data,
            )
            base = entry.definition.delivery_data(
                schema_version=entry.definition.schema_version,
                data=normalized,
            )
            return self._registry.blocks.apply_delivery_fields(
                storage_data=normalized,
                delivery_data=base,
                fields=entry.definition.block_fields,
            )
        except (InvalidRevisionDataError, SchemaError) as exc:
            raise self._invalid_data(revision.content_type, exc) from exc

    def _normalize_and_decode(
        self,
        entry: RegisteredContentTypeEntry,
        *,
        schema_version: int,
        data: RevisionData,
    ) -> tuple[RevisionData, object]:
        migrated = entry.definition.migrate_data(
            schema_version=schema_version,
            data=data,
        )
        normalized = self._registry.blocks.normalize_content_fields(
            migrated,
            entry.definition.block_fields,
        )
        value = entry.definition.decode_untyped(
            schema_version=entry.definition.schema_version,
            data=normalized,
        )
        return normalized, value

    def _require(self, type_key: ContentTypeKey) -> RegisteredContentTypeEntry:
        try:
            return self._registry.content_types.require(type_key)
        except ContentTypeNotFoundError as exc:
            raise ContentTypeUnavailableError(type_key) from exc

    @staticmethod
    def _invalid_data(
        type_key: ContentTypeKey,
        error: InvalidRevisionDataError | SchemaError,
    ) -> InvalidContentDataError:
        if isinstance(error, (ContentValidationError, BlockValidationError)):
            problems = tuple(
                ContentDataProblem(
                    code=issue.code,
                    message=issue.message,
                    path=issue.path,
                )
                for issue in error.issues
            )
        else:
            problems = (
                ContentDataProblem(
                    code="invalid_schema",
                    message=str(error),
                ),
            )
        return InvalidContentDataError(type_key=type_key, problems=problems)
