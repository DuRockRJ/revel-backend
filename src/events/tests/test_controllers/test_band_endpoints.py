import datetime

import orjson
import pytest
from django.test.client import Client
from django.urls import reverse
from django.utils import timezone

from events.models import Band, Event, OrganizationStaff

pytestmark = pytest.mark.django_db


class TestEventBandEndpoints:
    """Tests for band management on the EventAdminController."""

    def test_add_remove_clear_bands_by_owner(self, organization_owner_client: Client, event: Event) -> None:
        """Test that the event's organization owner can add, remove, and clear bands."""
        add_url = reverse("api:add_event_bands", kwargs={"event_id": event.pk})
        remove_url = reverse("api:remove_event_bands", kwargs={"event_id": event.pk})
        clear_url = reverse("api:clear_event_bands", kwargs={"event_id": event.pk})

        # Add bands, creating them on the fly
        add_payload = {"bands": ["Nirvana", "Foo Fighters "]}  # Note trailing space
        response_add = organization_owner_client.post(
            add_url, data=orjson.dumps(add_payload), content_type="application/json"
        )
        assert response_add.status_code == 200
        bands = {band["name"] for band in response_add.json()}
        assert bands == {"Nirvana", "Foo Fighters"}

        event.refresh_from_db()
        assert {band.name for band in event.bands.all()} == {"Nirvana", "Foo Fighters"}
        assert Band.objects.count() == 2

        # Adding the same band name again reuses the existing record (no duplicate)
        response_add_again = organization_owner_client.post(
            add_url, data=orjson.dumps({"bands": ["Nirvana"]}), content_type="application/json"
        )
        assert response_add_again.status_code == 200
        assert Band.objects.count() == 2

        # Remove a specific band
        remove_payload = {"bands": ["Nirvana"]}
        response_remove = organization_owner_client.post(
            remove_url, data=orjson.dumps(remove_payload), content_type="application/json"
        )
        assert response_remove.status_code == 200
        assert {band["name"] for band in response_remove.json()} == {"Foo Fighters"}
        event.refresh_from_db()
        assert {band.name for band in event.bands.all()} == {"Foo Fighters"}
        # The Band record itself still exists, only the event<->band link is gone
        assert Band.objects.filter(name="Nirvana").exists()

        # Clear all bands
        response_clear = organization_owner_client.delete(clear_url)
        assert response_clear.status_code == 204
        event.refresh_from_db()
        assert event.bands.count() == 0

    def test_add_bands_by_staff_with_permission(
        self, organization_staff_client: Client, event: Event, staff_member: OrganizationStaff
    ) -> None:
        """Test staff with 'edit_event' permission can add bands."""
        url = reverse("api:add_event_bands", kwargs={"event_id": event.pk})
        payload = {"bands": ["Staff Band"]}
        response = organization_staff_client.post(url, data=orjson.dumps(payload), content_type="application/json")
        assert response.status_code == 200
        assert "Staff Band" in [band["name"] for band in response.json()]

    def test_add_bands_by_staff_without_permission(
        self, organization_staff_client: Client, event: Event, staff_member: OrganizationStaff
    ) -> None:
        """Test staff without 'edit_event' permission gets 403."""
        perms = staff_member.permissions
        perms["default"]["edit_event"] = False
        staff_member.permissions = perms
        staff_member.save()

        url = reverse("api:add_event_bands", kwargs={"event_id": event.pk})
        payload = {"bands": ["Forbidden Band"]}
        response = organization_staff_client.post(url, data=orjson.dumps(payload), content_type="application/json")
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("member_client", 403),
            ("nonmember_client", 403),
            ("client", 401),
        ],
    )
    def test_add_bands_by_unauthorized_users(
        self, request: pytest.FixtureRequest, client_fixture: str, expected_status: int, event: Event
    ) -> None:
        """Test unauthorized users cannot add bands."""
        client: Client = request.getfixturevalue(client_fixture)
        url = reverse("api:add_event_bands", kwargs={"event_id": event.pk})
        payload = {"bands": ["Unauthorized Band"]}
        response = client.post(url, data=orjson.dumps(payload), content_type="application/json")
        assert response.status_code == expected_status


def test_list_bands_endpoint(client: Client) -> None:
    """Tests that the /api/bands/ endpoint correctly lists and searches for bands."""
    Band.objects.create(name="Nirvana")
    Band.objects.create(name="Foo Fighters")
    Band.objects.create(name="Metallica")

    list_url = reverse("api:list_bands")
    response_list = client.get(list_url)
    data_list = response_list.json()

    assert response_list.status_code == 200
    assert data_list["count"] == 3
    band_names = {band["name"] for band in data_list["results"]}
    assert {"Nirvana", "Foo Fighters", "Metallica"} == band_names

    search_url = f"{list_url}?search=Metal"
    response_search = client.get(search_url)
    data_search = response_search.json()

    assert response_search.status_code == 200
    assert data_search["count"] == 1
    assert data_search["results"][0]["name"] == "Metallica"


def test_filter_events_by_band(client: Client, event: Event) -> None:
    """Tests that events can be filtered by band name."""
    band = Band.objects.create(name="Nirvana")
    event.bands.add(band)
    event.start = timezone.now() + datetime.timedelta(days=7)
    event.end = event.start + datetime.timedelta(hours=3)
    event.save()

    list_url = reverse("api:list_events")
    response = client.get(list_url, {"bands": "Nirvana"})
    assert response.status_code == 200
    event_ids = {e["id"] for e in response.json()["results"]}
    assert str(event.pk) in event_ids

    response_no_match = client.get(list_url, {"bands": "Some Other Band"})
    assert response_no_match.status_code == 200
    event_ids_no_match = {e["id"] for e in response_no_match.json()["results"]}
    assert str(event.pk) not in event_ids_no_match
