import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from strata_cms.examples.simple_article import EXAMPLE_CONTENT_TYPE

pytestmark = pytest.mark.django_db


def _staff_client() -> APIClient:
    user_model = get_user_model()
    user = user_model.objects.create_superuser(
        username="editor",
        email="editor@example.invalid",
        password="test-password",
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _create_content(client: APIClient, *, title: str) -> dict[str, object]:
    response = client.post(
        reverse("api:management:content-create"),
        {
            "type": str(EXAMPLE_CONTENT_TYPE),
            "schema_version": 2,
            "data": {"title": title, "body": "Body"},
        },
        format="json",
    )
    created = response.json()
    assert isinstance(created, dict)
    return created


def _publish(client: APIClient, created: dict[str, object]) -> None:
    publish = client.post(
        reverse("api:management:content-publish", args=[created["content_id"]]),
        {
            "expected_version": created["content_version"],
            "revision_id": created["revision_id"],
        },
        format="json",
    )
    assert publish.status_code == 200


def test_attach_route_at_root() -> None:
    staff = _staff_client()
    created = _create_content(staff, title="About")

    response = staff.post(
        reverse("api:management:content-route", args=[created["content_id"]]),
        {"slug": "about"},
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["path"] == "about"
    assert body["parent_id"] is None


def test_get_route_returns_current_position() -> None:
    staff = _staff_client()
    created = _create_content(staff, title="About")
    staff.post(
        reverse("api:management:content-route", args=[created["content_id"]]),
        {"slug": "about"},
        format="json",
    )

    response = staff.get(
        reverse("api:management:content-route", args=[created["content_id"]])
    )

    assert response.status_code == 200
    assert response.json()["slug"] == "about"


def test_get_route_404s_when_not_attached() -> None:
    staff = _staff_client()
    created = _create_content(staff, title="Untouched")

    response = staff.get(
        reverse("api:management:content-route", args=[created["content_id"]])
    )

    assert response.status_code == 404


def test_attaching_a_second_route_is_a_conflict() -> None:
    staff = _staff_client()
    created = _create_content(staff, title="About")
    staff.post(
        reverse("api:management:content-route", args=[created["content_id"]]),
        {"slug": "about"},
        format="json",
    )

    response = staff.post(
        reverse("api:management:content-route", args=[created["content_id"]]),
        {"slug": "elsewhere"},
        format="json",
    )

    assert response.status_code == 409


def test_duplicate_sibling_slug_is_a_conflict() -> None:
    staff = _staff_client()
    first = _create_content(staff, title="About")
    second = _create_content(staff, title="About Too")
    staff.post(
        reverse("api:management:content-route", args=[first["content_id"]]),
        {"slug": "about"},
        format="json",
    )

    response = staff.post(
        reverse("api:management:content-route", args=[second["content_id"]]),
        {"slug": "about"},
        format="json",
    )

    assert response.status_code == 409


def test_move_route_updates_path_and_descendants() -> None:
    staff = _staff_client()
    about = _create_content(staff, title="About")
    company = _create_content(staff, title="Company")
    team = _create_content(staff, title="Team")
    staff.post(
        reverse("api:management:content-route", args=[about["content_id"]]),
        {"slug": "about"},
        format="json",
    )
    staff.post(
        reverse("api:management:content-route", args=[company["content_id"]]),
        {"slug": "company"},
        format="json",
    )
    staff.post(
        reverse("api:management:content-route", args=[team["content_id"]]),
        {"slug": "team", "parent_id": about["content_id"]},
        format="json",
    )

    move = staff.patch(
        reverse("api:management:content-route", args=[about["content_id"]]),
        {"slug": "about", "parent_id": company["content_id"], "expected_version": 0},
        format="json",
    )

    assert move.status_code == 200
    assert move.json()["path"] == "company/about"

    team_route = staff.get(
        reverse("api:management:content-route", args=[team["content_id"]])
    )
    assert team_route.status_code == 200


def test_move_route_rejects_cycle() -> None:
    staff = _staff_client()
    about = _create_content(staff, title="About")
    team = _create_content(staff, title="Team")
    staff.post(
        reverse("api:management:content-route", args=[about["content_id"]]),
        {"slug": "about"},
        format="json",
    )
    staff.post(
        reverse("api:management:content-route", args=[team["content_id"]]),
        {"slug": "team", "parent_id": about["content_id"]},
        format="json",
    )

    response = staff.patch(
        reverse("api:management:content-route", args=[about["content_id"]]),
        {"slug": "about", "parent_id": team["content_id"], "expected_version": 0},
        format="json",
    )

    assert response.status_code == 400


def test_detach_route_rejects_node_with_children() -> None:
    staff = _staff_client()
    about = _create_content(staff, title="About")
    team = _create_content(staff, title="Team")
    staff.post(
        reverse("api:management:content-route", args=[about["content_id"]]),
        {"slug": "about"},
        format="json",
    )
    staff.post(
        reverse("api:management:content-route", args=[team["content_id"]]),
        {"slug": "team", "parent_id": about["content_id"]},
        format="json",
    )

    response = staff.delete(
        reverse("api:management:content-route", args=[about["content_id"]]),
        {"expected_version": 0},
        format="json",
    )

    assert response.status_code == 409


def test_detach_leaf_route_succeeds() -> None:
    staff = _staff_client()
    about = _create_content(staff, title="About")
    staff.post(
        reverse("api:management:content-route", args=[about["content_id"]]),
        {"slug": "about"},
        format="json",
    )

    response = staff.delete(
        reverse("api:management:content-route", args=[about["content_id"]]),
        {"expected_version": 0},
        format="json",
    )

    assert response.status_code == 204


def test_delivery_resolves_published_route_path() -> None:
    staff = _staff_client()
    about = _create_content(staff, title="About Us")
    staff.post(
        reverse("api:management:content-route", args=[about["content_id"]]),
        {"slug": "about"},
        format="json",
    )
    _publish(staff, about)

    anonymous = APIClient()
    response = anonymous.get(reverse("api:delivery:route-detail", args=["about"]))

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "about"
    assert body["data"]["title"] == "About Us"


def test_delivery_route_404s_when_routed_but_unpublished() -> None:
    staff = _staff_client()
    about = _create_content(staff, title="About Us")
    staff.post(
        reverse("api:management:content-route", args=[about["content_id"]]),
        {"slug": "about"},
        format="json",
    )

    anonymous = APIClient()
    response = anonymous.get(reverse("api:delivery:route-detail", args=["about"]))

    assert response.status_code == 404


def test_delivery_resolves_nested_route_path() -> None:
    staff = _staff_client()
    about = _create_content(staff, title="About")
    team = _create_content(staff, title="Our Team")
    staff.post(
        reverse("api:management:content-route", args=[about["content_id"]]),
        {"slug": "about"},
        format="json",
    )
    staff.post(
        reverse("api:management:content-route", args=[team["content_id"]]),
        {"slug": "team", "parent_id": about["content_id"]},
        format="json",
    )
    _publish(staff, team)

    anonymous = APIClient()
    response = anonymous.get(reverse("api:delivery:route-detail", args=["about/team"]))

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Our Team"


def test_route_write_endpoints_reject_non_staff_users() -> None:
    client = APIClient()

    response = client.post(
        reverse(
            "api:management:content-route",
            args=["00000000-0000-0000-0000-000000000000"],
        ),
        {"slug": "about"},
        format="json",
    )

    assert response.status_code in {401, 403}
