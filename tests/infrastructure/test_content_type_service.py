from datetime import UTC, datetime
from uuid import UUID

import pytest

from strata_cms.application.errors import (
    ContentTypeUnavailableError,
    InvalidContentDataError,
)
from strata_cms.domain.revision import Revision, RevisionData
from strata_cms.domain.value_objects import (
    ActorId,
    ContentId,
    ContentTypeKey,
    RevisionId,
)
from strata_cms.examples.simple_article import (
    EXAMPLE_CONTENT_TYPE,
    register_example,
)
from strata_cms.examples.structured_page import LANDING_PAGE_TYPE
from strata_cms.infrastructure.content_types import RegistryContentTypeService
from strata_cms.plugin_api import StrataRegistryBuilder


def _service() -> RegistryContentTypeService:
    builder = StrataRegistryBuilder()
    register_example(builder)
    return RegistryContentTypeService(builder.build(strata_version="0.1.0"))


def test_prepare_for_write_upgrades_to_current_schema() -> None:
    prepared = _service().prepare_for_write(
        type_key=EXAMPLE_CONTENT_TYPE,
        schema_version=1,
        data={"heading": "Old title", "body": "Text"},
    )

    assert prepared.schema_version == 2
    assert prepared.data.as_dict() == {"title": "Old title", "body": "Text"}


def test_delivery_data_migrates_historical_revision() -> None:
    revision = Revision(
        id=RevisionId(UUID(int=2)),
        content_id=ContentId(UUID(int=1)),
        number=1,
        content_type=EXAMPLE_CONTENT_TYPE,
        schema_version=1,
        data=RevisionData.from_mapping({"heading": "Old title", "body": "Text"}),
        created_at=datetime(2026, 9, 12, tzinfo=UTC),
        created_by=ActorId("user:1"),
    )

    assert _service().delivery_data(revision) == {
        "title": "Old title",
        "body": "Text",
        "kind": "article",
    }


def test_prepare_for_write_translates_validation_errors() -> None:
    service = _service()

    with pytest.raises(InvalidContentDataError) as raised:
        service.prepare_for_write(
            type_key=EXAMPLE_CONTENT_TYPE,
            schema_version=2,
            data={"title": "  ", "body": "Text"},
        )

    assert raised.value.problems[0].code == "title_required"
    assert raised.value.problems[0].path == "$.title"


def test_prepare_for_write_translates_unknown_content_type() -> None:
    service = _service()

    with pytest.raises(ContentTypeUnavailableError) as raised:
        service.prepare_for_write(
            type_key=ContentTypeKey("tests.unknown"),
            schema_version=1,
            data={},
        )

    assert str(raised.value.type_key) == "tests.unknown"


def test_structured_content_write_normalizes_nested_block_versions() -> None:
    prepared = _service().prepare_for_write(
        type_key=LANDING_PAGE_TYPE,
        schema_version=1,
        data={
            "title": "Blocks",
            "body": [
                {
                    "id": "00000000-0000-0000-0000-000000000101",
                    "type": "strata_examples.text",
                    "version": 1,
                    "data": {"value": "Historical text"},
                    "slots": {},
                }
            ],
        },
    )

    body = prepared.data.as_dict()["body"]
    assert isinstance(body, list)
    assert body[0]["version"] == 2
    assert body[0]["data"] == {"text": "Historical text"}


def test_structured_content_delivery_uses_block_delivery_serializers() -> None:
    revision = Revision(
        id=RevisionId(UUID(int=12)),
        content_id=ContentId(UUID(int=11)),
        number=1,
        content_type=LANDING_PAGE_TYPE,
        schema_version=1,
        data=RevisionData.from_mapping(
            {
                "title": "Blocks",
                "body": [
                    {
                        "id": "00000000-0000-0000-0000-000000000101",
                        "type": "strata_examples.text",
                        "version": 1,
                        "data": {"value": "Historical text"},
                        "slots": {},
                    }
                ],
            }
        ),
        created_at=datetime(2026, 9, 12, tzinfo=UTC),
        created_by=ActorId("user:1"),
    )

    assert _service().delivery_data(revision) == {
        "title": "Blocks",
        "kind": "landing_page",
        "body": [
            {
                "id": "00000000-0000-0000-0000-000000000101",
                "type": "strata_examples.text",
                "data": {"text": "Historical text", "kind": "text"},
                "slots": {},
            }
        ],
    }
