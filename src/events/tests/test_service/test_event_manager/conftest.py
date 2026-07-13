"""Shared fixtures for event_manager tests."""

import pytest

from events.models import TicketTier


@pytest.fixture(autouse=True)
def _default_tier_for_ticketed_events(request: pytest.FixtureRequest) -> None:
    """Give any requested ticketed event fixture an open ticket tier.

    Most tests here exercise gates unrelated to ticket sales (blacklist, deadlines,
    questionnaires, ...) via the full `EligibilityService.check_eligibility()` chain.
    Events used to always get a tier auto-created on save; now that this is opt-in,
    an event with zero tiers is correctly denied by `TicketSalesGate` — which would
    otherwise mask the gate these tests actually target. Tests that care about tier
    setup themselves (e.g. `test_ticket_sales_window.py`) already delete/create tiers
    explicitly, so this is a no-op for them.
    """
    for fixture_name in ("private_event", "public_event", "members_only_event"):
        if fixture_name in request.fixturenames:
            event = request.getfixturevalue(fixture_name)
            if event.requires_ticket and not event.ticket_tiers.exists():
                TicketTier.objects.create(event=event, name="Autouse Default Tier")
