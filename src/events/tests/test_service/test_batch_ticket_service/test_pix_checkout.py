"""Tests for BatchTicketService Pix checkout (_pix_checkout / build_pix_checkout_response_fields)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from ninja.errors import HttpError

from accounts.models import RevelUser
from events.models import Event, Organization, Ticket, TicketTier
from events.schema import TicketPurchaseItem
from events.service.batch_ticket_service import BatchTicketService, build_pix_checkout_response_fields

pytestmark = pytest.mark.django_db


@pytest.fixture
def event(organization: Organization) -> Event:
    return Event.objects.create(
        organization=organization,
        name="Test Event",
        slug="test-event",
        event_type=Event.EventType.PUBLIC,
        start=timezone.now() + timedelta(days=7),
        status=Event.EventStatus.OPEN,
        visibility=Event.Visibility.PUBLIC,
        max_tickets_per_user=5,
    )


@pytest.fixture
def pix_tier(event: Event) -> TicketTier:
    return TicketTier.objects.create(
        event=event,
        name="Pix Entry",
        price=Decimal("25.00"),
        currency="BRL",
        payment_method=TicketTier.PaymentMethod.PIX,
        total_quantity=100,
    )


class TestPixCheckout:
    def test_pix_checkout_requires_organization_pix_key(
        self, event: Event, pix_tier: TicketTier, member_user: RevelUser
    ) -> None:
        """Purchasing a Pix tier for an organization without a configured Pix key must fail clearly."""
        assert not event.organization.pix_key
        service = BatchTicketService(event, pix_tier, member_user)

        with pytest.raises(HttpError):
            service.create_batch([TicketPurchaseItem(guest_name="Guest 1")])

    def test_pix_checkout_creates_pending_tickets_with_shared_reference(
        self, event: Event, pix_tier: TicketTier, member_user: RevelUser
    ) -> None:
        event.organization.pix_key = "org@example.com"
        event.organization.save()

        service = BatchTicketService(event, pix_tier, member_user)
        result = service.create_batch(
            [TicketPurchaseItem(guest_name="Guest 1"), TicketPurchaseItem(guest_name="Guest 2")]
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(t.status == Ticket.TicketStatus.PENDING for t in result)
        # Both tickets in the batch share one reference (one QR covers the whole checkout).
        assert result[0].pix_reference
        assert result[0].pix_reference == result[1].pix_reference
        assert len(result[0].pix_reference) == 8

    def test_pix_checkout_updates_quantity_sold(
        self, event: Event, pix_tier: TicketTier, member_user: RevelUser
    ) -> None:
        event.organization.pix_key = "org@example.com"
        event.organization.save()

        service = BatchTicketService(event, pix_tier, member_user)
        service.create_batch([TicketPurchaseItem(guest_name="Guest 1"), TicketPurchaseItem(guest_name="Guest 2")])

        pix_tier.refresh_from_db()
        assert pix_tier.quantity_sold == 2


class TestBuildPixCheckoutResponseFields:
    def test_returns_payload_and_qr_for_the_batch_total(
        self, event: Event, pix_tier: TicketTier, member_user: RevelUser
    ) -> None:
        event.organization.pix_key = "11144477735"
        event.organization.billing_name = "Meu Bar"
        event.organization.save()

        service = BatchTicketService(event, pix_tier, member_user)
        tickets = service.create_batch(
            [TicketPurchaseItem(guest_name="Guest 1"), TicketPurchaseItem(guest_name="Guest 2")]
        )
        assert isinstance(tickets, list)

        payload, qr_data_uri = build_pix_checkout_response_fields(tickets)

        assert "11144477735" in payload
        assert "MEU BAR" in payload
        assert tickets[0].pix_reference in payload
        # Two tickets at 25.00 each -> one combined 50.00 payment (amount field: tag 54, len 05, "50.00").
        assert "540550.00" in payload
        assert qr_data_uri.startswith("data:image/png;base64,")
