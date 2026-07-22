"""Tests for the external event-ingestion endpoint (e.g. rockfeed-rj scraper)."""

import typing as t
from decimal import Decimal
from unittest.mock import ANY, patch

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from accounts.models import RevelUser
from events.models import Event, Organization, TicketTier, Venue
from events.service.external_ingest_service import SCRAPER_SYSTEM_USERNAME, UNCLASSIFIED_ORG_NAME

pytestmark = pytest.mark.django_db

INGEST_URL_NAME = "api:ingest_events"


@pytest.fixture(autouse=True)
def _ingest_api_key(settings: t.Any) -> None:
    settings.EXTERNAL_INGEST_API_KEY = "test-shared-secret"


def _payload(**overrides: t.Any) -> dict[str, t.Any]:
    base = {
        "uid": "abc123",
        "title": "Show da Banda X",
        "url": "https://sympla.com.br/show-da-banda-x",
        "source": "sympla",
        "venue": "Vivo Rio",
        "address": "Av. Infante Dom Henrique 85",
        "organizer": "",
        "city": "Rio de Janeiro",
        "date": "2026-08-15T22:00:00-03:00",
        "end_date": "",
        "price": "R$ 80,00",
        "image": "",
        "description": "Um baita show.",
    }
    base.update(overrides)
    return base


def _post(client: Client, items: list[dict[str, t.Any]], key: str = "test-shared-secret") -> t.Any:
    return client.post(
        reverse(INGEST_URL_NAME),
        data=items,
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {key}",
    )


class TestExternalIngestAuth:
    def test_missing_credentials_rejected(self, client: Client) -> None:
        response = client.post(reverse(INGEST_URL_NAME), data=[_payload()], content_type="application/json")
        assert response.status_code == 401

    def test_wrong_key_rejected(self, client: Client) -> None:
        response = _post(client, [_payload()], key="wrong-key")
        assert response.status_code == 401

    @override_settings(EXTERNAL_INGEST_API_KEY="")
    def test_endpoint_disabled_when_no_key_configured(self, client: Client) -> None:
        response = _post(client, [_payload()])
        assert response.status_code == 401


class TestExternalIngestEvents:
    def test_creates_event_with_placeholder_org_when_no_organizer(self, client: Client) -> None:
        response = _post(client, [_payload(uid="no-organizer-uid", organizer="")])

        assert response.status_code == 200
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["uid"] == "no-organizer-uid"
        assert results[0]["action"] == "created"

        event = Event.objects.get(external_uid="no-organizer-uid")
        assert str(event.id) == results[0]["event_id"]
        assert event.status == Event.EventStatus.DRAFT
        assert event.organization.name == UNCLASSIFIED_ORG_NAME
        assert event.name == "Show da Banda X"
        assert "Vivo Rio" in (event.address or "")

        tier = TicketTier.objects.get(event=event)
        assert tier.payment_method == TicketTier.PaymentMethod.EXTERNAL
        assert tier.external_ticket_url == "https://sympla.com.br/show-da-banda-x"
        assert tier.price == Decimal("80.00")
        assert tier.name == "Sympla"

    def test_titlecases_fully_uppercase_title(self, client: Client) -> None:
        response = _post(client, [_payload(uid="shouting-uid", title="TRIBUTO AO IRON MAIDEN COM A SHE BEAST!")])

        assert response.status_code == 200
        event = Event.objects.get(external_uid="shouting-uid")
        assert event.name == "Tributo Ao Iron Maiden Com A She Beast!"

    def test_leaves_mixed_case_title_untouched(self, client: Client) -> None:
        _post(client, [_payload(uid="mixed-case-uid", title="SanforRock")])

        event = Event.objects.get(external_uid="mixed-case-uid")
        assert event.name == "SanforRock"

    def test_tier_name_uses_platform_before_colon(self, client: Client) -> None:
        _post(client, [_payload(uid="meaple-uid", source="meaple:orockvive")])

        event = Event.objects.get(external_uid="meaple-uid")
        tier = TicketTier.objects.get(event=event)
        assert tier.name == "Meaple"

    def test_tier_name_overrides_clubedoingresso(self, client: Client) -> None:
        _post(client, [_payload(uid="cdi-uid", source="clubedoingresso")])

        event = Event.objects.get(external_uid="cdi-uid")
        tier = TicketTier.objects.get(event=event)
        assert tier.name == "Clube do Ingresso"

    def test_tier_name_overrides_sympla_eventos(self, client: Client) -> None:
        _post(client, [_payload(uid="sympla-eventos-uid", source="sympla_eventos")])

        event = Event.objects.get(external_uid="sympla-eventos-uid")
        tier = TicketTier.objects.get(event=event)
        assert tier.name == "Sympla"

    def test_links_default_venue_when_organization_has_exactly_one(self, client: Client, user: RevelUser) -> None:
        org = Organization.objects.create(name="Coordenadas Bar", owner=user)
        venue = Venue.objects.create(organization=org, name="Coordenadas Bar")

        _post(client, [_payload(uid="venue-uid", organizer="Coordenadas Bar")])

        event = Event.objects.get(external_uid="venue-uid")
        assert event.venue_id == venue.id

    def test_does_not_link_venue_when_organization_has_multiple_venues(self, client: Client, user: RevelUser) -> None:
        org = Organization.objects.create(name="Multi Venue Org", owner=user)
        Venue.objects.create(organization=org, name="Palco A")
        Venue.objects.create(organization=org, name="Palco B")

        _post(client, [_payload(uid="multi-venue-uid", organizer="Multi Venue Org")])

        event = Event.objects.get(external_uid="multi-venue-uid")
        assert event.venue_id is None

    def test_creates_organization_for_new_organizer(self, client: Client) -> None:
        response = _post(client, [_payload(uid="organizer-uid", organizer="Central do Rock Produções")])

        assert response.status_code == 200
        event = Event.objects.get(external_uid="organizer-uid")
        assert event.organization.name == "Central do Rock Produções"
        assert event.organization.owner.username == SCRAPER_SYSTEM_USERNAME
        assert event.organization.visibility == Organization.Visibility.STAFF_ONLY

    def test_reuses_existing_organization_by_name(self, client: Client) -> None:
        _post(client, [_payload(uid="uid-1", organizer="Mesma Produtora")])
        _post(client, [_payload(uid="uid-2", organizer="Mesma Produtora")])

        org_count = Organization.objects.filter(name="Mesma Produtora").count()
        assert org_count == 1

    def test_reingestion_updates_draft_event(self, client: Client) -> None:
        _post(client, [_payload(uid="update-me", title="Título Original", price="R$ 50,00")])
        response = _post(client, [_payload(uid="update-me", title="Título Atualizado", price="R$ 60,00")])

        assert response.json()["results"][0]["action"] == "updated"
        event = Event.objects.get(external_uid="update-me")
        assert event.name == "Título Atualizado"
        tier = TicketTier.objects.get(event=event)
        assert tier.price == Decimal("60.00")
        assert tier.name == "Sympla"
        assert Event.objects.filter(external_uid="update-me").count() == 1
        assert TicketTier.objects.filter(event=event).count() == 1

    def test_reingestion_skips_published_event(self, client: Client) -> None:
        _post(client, [_payload(uid="published-uid", title="Título Original")])
        event = Event.objects.get(external_uid="published-uid")
        event.status = Event.EventStatus.OPEN
        event.save()

        response = _post(client, [_payload(uid="published-uid", title="Tentativa De Sobrescrever")])

        assert response.json()["results"][0]["action"] == "skipped"
        event.refresh_from_db()
        assert event.name == "Título Original"

    def test_reingestion_keeps_previous_organization_when_organizer_now_empty(self, client: Client) -> None:
        _post(client, [_payload(uid="keep-org-uid", organizer="Produtora Confiável")])
        _post(client, [_payload(uid="keep-org-uid", organizer="")])

        event = Event.objects.get(external_uid="keep-org-uid")
        assert event.organization.name == "Produtora Confiável"

    def test_dispatches_cover_art_task_when_image_present(
        self, client: Client, django_capture_on_commit_callbacks: t.Any
    ) -> None:
        with patch("events.service.external_ingest_service.fetch_external_cover_art.delay") as mock_delay:
            with django_capture_on_commit_callbacks(execute=True):
                _post(client, [_payload(uid="img-uid", image="https://files.meaple.com.br/x.jpg")])

        event = Event.objects.get(external_uid="img-uid")
        mock_delay.assert_called_once_with(str(event.id), "https://files.meaple.com.br/x.jpg", ANY)

    def test_does_not_dispatch_cover_art_task_when_no_image(
        self, client: Client, django_capture_on_commit_callbacks: t.Any
    ) -> None:
        with patch("events.service.external_ingest_service.fetch_external_cover_art.delay") as mock_delay:
            with django_capture_on_commit_callbacks(execute=True):
                _post(client, [_payload(uid="no-img-uid", image="")])
        mock_delay.assert_not_called()

    def test_missing_date_reports_error_without_failing_batch(self, client: Client) -> None:
        response = _post(
            client,
            [
                _payload(uid="bad-date-uid", date=""),
                _payload(uid="good-date-uid"),
            ],
        )

        assert response.status_code == 200
        results = {r["uid"]: r for r in response.json()["results"]}
        assert results["bad-date-uid"]["action"] == "error"
        assert not Event.objects.filter(external_uid="bad-date-uid").exists()
        assert Event.objects.filter(external_uid="good-date-uid").exists()
