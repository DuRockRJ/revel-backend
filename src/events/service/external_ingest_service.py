"""Ingestion of scraped events from external sources (e.g. the rockfeed-rj scraper).

Events are always created as DRAFT for manual review. Re-ingesting the same
``external_uid`` updates the event only while it remains DRAFT; once an admin
publishes it (any other status), re-ingestion leaves it untouched.
"""

import re
import typing as t
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import RevelUser
from common.utils import get_or_create_with_race_protection
from events.models import DEFAULT_TICKET_TIER_NAME, Event, Organization, TicketTier
from events.schema import EventIngestResultSchema, EventIngestSchema

SCRAPER_SYSTEM_USERNAME = "scraper-system@durockrj.com.br"
UNCLASSIFIED_ORG_NAME = "Não classificado"

# rockfeed-rj's own scrapers attach a fixed UTC-3 offset when a source doesn't
# provide one (Brazil has had no DST since 2019). A naive datetime reaching
# this endpoint is assumed to already be in that local time, not the Django
# server's configured TIME_ZONE.
_BRAZIL_TZ = dt_timezone(timedelta(hours=-3))

_PRICE_RE = re.compile(r"\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?")


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, _BRAZIL_TZ)
    return parsed


def _parse_price(raw: str) -> Decimal:
    """Best-effort extraction of a numeric price from freeform BR currency text.

    # ponytail: falls back to 0 on anything unparseable ("a partir de R$ 40",
    # "gratuito", ranges, ...). Price here is a convenience for draft review,
    # not billing-critical — the organizer confirms the real price before
    # publishing. Upgrade path: parse ranges/free-entry text explicitly if
    # this ever needs to be accurate without manual review.
    """
    if not raw:
        return Decimal("0")
    match = _PRICE_RE.search(raw)
    if not match:
        return Decimal("0")
    normalized = match.group().replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return Decimal("0")


def _build_address(item: EventIngestSchema) -> str:
    """Combine venue/address/city into one plain-text field.

    Deliberately not matched against real Venue/City records — free text
    from a scraper is too fragile to auto-link; the organizer relinks it
    manually (if at all) after reviewing the draft.
    """
    parts = [item.venue.strip(), item.address.strip(), item.city.strip()]
    return ", ".join(p for p in parts if p)


def _get_system_user() -> RevelUser:
    return RevelUser.objects.get(username=SCRAPER_SYSTEM_USERNAME)


def _resolve_organization(organizer: str) -> Organization:
    name = organizer.strip()
    if not name:
        return Organization.objects.get(name=UNCLASSIFIED_ORG_NAME)
    organization, _created = get_or_create_with_race_protection(
        Organization,
        Q(name__iexact=name),
        {
            "name": name,
            "owner": _get_system_user(),
            "visibility": Organization.Visibility.STAFF_ONLY,
        },
    )
    return organization


def ingest_events(items: list[EventIngestSchema]) -> list[EventIngestResultSchema]:
    """Ingest a batch of scraped events. Each item is handled independently."""
    return [_ingest_one(item) for item in items]


def _ingest_one(item: EventIngestSchema) -> EventIngestResultSchema:
    start = _parse_datetime(item.date)
    if start is None:
        return EventIngestResultSchema(uid=item.uid, action="error", detail="Missing or invalid 'date'")
    # Event.end is non-nullable; default to start + 1 day when the source has no end time.
    end = _parse_datetime(item.end_date) or start + timedelta(days=1)

    existing = Event.objects.filter(external_uid=item.uid).first()
    if existing and existing.status != Event.EventStatus.DRAFT:
        return EventIngestResultSchema(uid=item.uid, action="skipped", event_id=existing.id)

    address = _build_address(item)
    action: t.Literal["created", "updated"]

    with transaction.atomic():
        if existing:
            # Don't regress a previously-resolved organizer back to the
            # placeholder just because this scrape came back empty.
            if item.organizer.strip():
                existing.organization = _resolve_organization(item.organizer)
            existing.name = item.title
            existing.start = start
            existing.end = end
            existing.address = address or None
            existing.description = item.description or None
            existing.save()
            event = existing
            action = "updated"
        else:
            event = Event.objects.create(
                organization=_resolve_organization(item.organizer),
                external_uid=item.uid,
                name=item.title,
                status=Event.EventStatus.DRAFT,
                event_type=Event.EventType.PUBLIC,
                visibility=Event.Visibility.PUBLIC,
                start=start,
                end=end,
                address=address or None,
                description=item.description or None,
            )
            action = "created"

        TicketTier.objects.update_or_create(
            event=event,
            name=DEFAULT_TICKET_TIER_NAME,
            defaults={
                "payment_method": TicketTier.PaymentMethod.EXTERNAL,
                "external_ticket_url": item.url,
                "price": _parse_price(item.price),
            },
        )

    return EventIngestResultSchema(uid=item.uid, action=action, event_id=event.id)
