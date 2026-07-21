"""Schemas for the external event-ingestion endpoint (e.g. rockfeed-rj scraper)."""

import typing as t
from uuid import UUID

from ninja import Schema


class EventIngestSchema(Schema):
    """One scraped event, as produced by rockfeed-rj's ``GET /events.json``.

    Dates are kept as raw strings (not ``AwareDatetime``): upstream scrapers don't
    all guarantee a timezone offset, so parsing/defaulting is done leniently in
    the service layer instead of rejecting the whole batch on one malformed item.
    """

    uid: str
    title: str
    url: str
    source: str
    venue: str = ""
    address: str = ""
    organizer: str = ""
    city: str = ""
    date: str | None = None
    end_date: str | None = None
    price: str = ""
    image: str = ""
    description: str = ""


class EventIngestResultSchema(Schema):
    """Outcome of ingesting a single event."""

    uid: str
    action: t.Literal["created", "updated", "skipped", "error"]
    event_id: UUID | None = None
    detail: str = ""


class EventIngestResponseSchema(Schema):
    """Bulk ingestion response: one result per submitted event."""

    results: list[EventIngestResultSchema]
