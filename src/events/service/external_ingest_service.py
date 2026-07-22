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
from events.models import DEFAULT_TICKET_TIER_NAME, Event, Organization, TicketTier, Venue
from events.schema import EventIngestResultSchema, EventIngestSchema
from events.tasks.external_ingest import fetch_external_cover_art

SCRAPER_SYSTEM_USERNAME = "scraper-system@durockrj.com.br"
UNCLASSIFIED_ORG_NAME = "Não classificado"

# rockfeed-rj's own scrapers attach a fixed UTC-3 offset when a source doesn't
# provide one (Brazil has had no DST since 2019). A naive datetime reaching
# this endpoint is assumed to already be in that local time, not the Django
# server's configured TIME_ZONE.
_BRAZIL_TZ = dt_timezone(timedelta(hours=-3))

_PRICE_RE = re.compile(r"\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?")

# Platform slugs whose default `.capitalize()` reads badly as a tier name.
_TIER_NAME_OVERRIDES = {
    "clubedoingresso": "Clube do Ingresso",
    "sympla_eventos": "Sympla",
}


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


def _tier_name_from_source(source: str) -> str:
    """Human-friendly ticket tier name from the scraper source, e.g. 'sympla:drunkspubcg' -> 'Sympla'."""
    platform = source.split(":", 1)[0].strip().lower()
    if not platform:
        return DEFAULT_TICKET_TIER_NAME
    return _TIER_NAME_OVERRIDES.get(platform, platform.capitalize())


def _normalize_title(title: str) -> str:
    """Title-case a fully-uppercase scraped title; leave anything else as-is.

    Sources often send show titles SHOUTING IN ALL CAPS. Mixed-case titles
    (including intentional stylizations) are the organizer's choice, not
    ours to "fix", so only the all-caps case is touched.
    """
    return title.title() if title.isupper() else title


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


def _resolve_default_venue(organization: Organization) -> Venue | None:
    """Return the org's Venue if it has exactly one.

    Treated as the default venue for its ingested events (e.g. a bar that
    only ever hosts its own shows). Ambiguous (zero or several venues) ->
    leave unset, don't guess.
    """
    venues = list(Venue.objects.filter(organization=organization)[:2])
    return venues[0] if len(venues) == 1 else None


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
            # Organization is set once, at creation, and never touched again:
            # re-resolving on every scrape risks creating a near-duplicate org
            # for minor organizer-text drift, and would clobber a manual
            # reassignment made while reviewing the draft.
            existing.name = _normalize_title(item.title)
            existing.start = start
            existing.end = end
            existing.address = address or None
            existing.description = item.description or None
            existing.venue = _resolve_default_venue(existing.organization)
            existing.save()
            event = existing
            action = "updated"
        else:
            organization = _resolve_organization(item.organizer)
            event = Event.objects.create(
                organization=organization,
                venue=_resolve_default_venue(organization),
                external_uid=item.uid,
                name=_normalize_title(item.title),
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
            payment_method=TicketTier.PaymentMethod.EXTERNAL,
            defaults={
                "name": _tier_name_from_source(item.source),
                "external_ticket_url": item.url,
                "price": _parse_price(item.price),
            },
        )

        # Best-effort cover art, dispatched async so a slow/dead image host can't
        # stall a bulk POST. Only when missing — avoids re-downloading and
        # re-triggering thumbnail generation on every re-ingestion of an
        # unchanged image. Deferred to on_commit: ATOMIC_REQUESTS wraps this
        # whole request in a transaction, so a worker could otherwise pick the
        # task up before the row is visible.
        if item.image and not event.cover_art:
            system_user_id = str(_get_system_user().id)
            event_id = str(event.id)
            image_url = item.image
            transaction.on_commit(lambda: fetch_external_cover_art.delay(event_id, image_url, system_user_id))

    return EventIngestResultSchema(uid=item.uid, action=action, event_id=event.id)
