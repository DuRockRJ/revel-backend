"""Public ticket-tier listing schema tests."""

import typing as t

import pytest
from django.conf import settings
from django.test.client import Client
from django.urls import reverse

from events.models import Event, TicketTier

pytestmark = pytest.mark.django_db


def test_list_tiers_exposes_cancellation_policy_fields(
    client: Client,
    public_event: Event,
    tier_factory: t.Callable[..., TicketTier],
) -> None:
    """Buyers must see cancellation/refund policy *before* committing (issue #382)."""
    refund_policy = {
        "tiers": [
            {"hours_before_event": 48, "refund_percentage": "100"},
            {"hours_before_event": 24, "refund_percentage": "50"},
        ],
        "flat_fee": "1.00",
    }
    tier_factory(
        event=public_event,
        name="Cancellable",
        purchasable_by=TicketTier.PurchasableBy.PUBLIC,
        allow_user_cancellation=True,
        cancellation_deadline_hours=24,
        refund_policy=refund_policy,
    )

    response = client.get(reverse("api:tier_list", kwargs={"event_id": public_event.pk}))

    assert response.status_code == 200, response.content
    body = response.json()
    cancellable = next(t for t in body if t["name"] == "Cancellable")
    assert cancellable["allow_user_cancellation"] is True
    assert cancellable["cancellation_deadline_hours"] == 24
    assert cancellable["refund_policy"] == {
        "tiers": [
            {"hours_before_event": 48, "refund_percentage": "100"},
            {"hours_before_event": 24, "refund_percentage": "50"},
        ],
        "flat_fee": "1.00",
    }


def test_list_tiers_defaults_when_cancellation_disabled(
    client: Client,
    public_event: Event,
    tier_factory: t.Callable[..., TicketTier],
) -> None:
    """Tiers without a refund policy serialize defaults — no 500, no missing keys."""
    tier_factory(
        event=public_event,
        name="No-Cancel",
        purchasable_by=TicketTier.PurchasableBy.PUBLIC,
    )

    response = client.get(reverse("api:tier_list", kwargs={"event_id": public_event.pk}))

    assert response.status_code == 200, response.content
    body = response.json()
    no_cancel = next(t for t in body if t["name"] == "No-Cancel")
    assert no_cancel["allow_user_cancellation"] is False
    assert no_cancel["cancellation_deadline_hours"] is None
    assert no_cancel["refund_policy"] is None


def test_list_tiers_exposes_buyer_fee_for_online_tier(
    client: Client,
    public_event: Event,
    tier_factory: t.Callable[..., TicketTier],
) -> None:
    """Online tiers expose the buyer-fee rate ingredients (issue: fee shown to buyer, not organizer)."""
    public_event.organization.platform_fee_percent = 3
    public_event.organization.platform_fee_fixed = 0
    public_event.organization.save()
    tier_factory(
        event=public_event,
        name="Online Tier",
        purchasable_by=TicketTier.PurchasableBy.PUBLIC,
        payment_method=TicketTier.PaymentMethod.ONLINE,
        # Matches settings.DEFAULT_CURRENCY so the fixed-fee conversion short-circuits
        # (same currency) instead of needing a seeded cross-currency ExchangeRate row.
        currency=settings.DEFAULT_CURRENCY,
    )

    response = client.get(reverse("api:tier_list", kwargs={"event_id": public_event.pk}))

    assert response.status_code == 200, response.content
    online = next(t for t in response.json() if t["name"] == "Online Tier")
    assert online["buyer_fee_percent"] == "3.00"
    assert online["buyer_fee_fixed_amount"] == "0.00"
    assert online["buyer_fee_vat_rate"] is not None


def test_list_tiers_hides_buyer_fee_for_offline_tier(
    client: Client,
    public_event: Event,
    tier_factory: t.Callable[..., TicketTier],
) -> None:
    """Offline/at-the-door/external tiers never pass the platform fee to the buyer."""
    tier_factory(
        event=public_event,
        name="Offline Tier",
        purchasable_by=TicketTier.PurchasableBy.PUBLIC,
        payment_method=TicketTier.PaymentMethod.OFFLINE,
    )

    response = client.get(reverse("api:tier_list", kwargs={"event_id": public_event.pk}))

    assert response.status_code == 200, response.content
    offline = next(t for t in response.json() if t["name"] == "Offline Tier")
    assert offline["buyer_fee_percent"] is None
    assert offline["buyer_fee_fixed_amount"] is None
    assert offline["buyer_fee_vat_rate"] is None
