"""Celery task for best-effort cover-art import during external event ingestion."""

from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import urlparse

import httpx
import structlog
from celery import shared_task
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from PIL import Image

from accounts.models import RevelUser
from common.fields import ALLOWED_IMAGE_EXTENSIONS, MAX_IMAGE_SIZE_BYTES
from common.utils import safe_save_uploaded_file
from events.models import Event

logger = structlog.get_logger(__name__)

_DOWNLOAD_TIMEOUT_SECONDS = 15

# Below this, treat the source image as a placeholder/logo rather than a real
# cover photo (observed in practice: venue logos at 166x166/222x222, and a
# handful of literal 1x1 blank placeholders from some sources).
_MIN_COVER_ART_WIDTH = 300
_MIN_COVER_ART_HEIGHT = 150


def _filename_from_url(url: str, fallback_stem: str) -> str:
    suffix = PurePosixPath(urlparse(url).path).suffix.lower().lstrip(".")
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        suffix = "jpg"
    return f"{fallback_stem}.{suffix}"


def _dimensions(content: bytes) -> tuple[int, int] | None:
    try:
        with Image.open(BytesIO(content)) as img:
            return img.size
    except Exception:
        return None


@shared_task(
    name="events.tasks.fetch_external_cover_art",
    autoretry_for=(httpx.TransportError,),
    max_retries=2,
    default_retry_delay=30,
)
def fetch_external_cover_art(event_id: str, image_url: str, uploader_id: str) -> None:
    """Download a scraped event's image and attach it as cover art.

    Runs async (not inline with ingestion) so a slow/unreachable image host
    can't stall a bulk POST from the scraper. Best-effort: a bad response
    (404, oversized, not a real image) is logged and dropped, not retried.
    Connection-level failures (``httpx.TransportError``) are retried by
    Celery via ``autoretry_for``.

    No-ops if the event was deleted, published (an admin already reviewed
    it — don't touch it), or already has cover art (e.g. a concurrent
    re-ingestion already set one).
    """
    event = Event.objects.filter(pk=event_id).first()
    if event is None or event.status != Event.EventStatus.DRAFT or event.cover_art:
        return

    try:
        response = httpx.get(image_url, timeout=_DOWNLOAD_TIMEOUT_SECONDS, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPStatusError:
        logger.info("external_ingest_cover_art_download_failed", event_id=event_id, url=image_url)
        return

    if len(response.content) > MAX_IMAGE_SIZE_BYTES:
        logger.info("external_ingest_cover_art_too_large", event_id=event_id, url=image_url)
        return

    dimensions = _dimensions(response.content)
    if dimensions is None:
        logger.info("external_ingest_cover_art_unreadable", event_id=event_id, url=image_url)
        return
    width, height = dimensions
    if width < _MIN_COVER_ART_WIDTH or height < _MIN_COVER_ART_HEIGHT:
        logger.info("external_ingest_cover_art_too_small", event_id=event_id, url=image_url, width=width, height=height)
        return

    uploader = RevelUser.objects.filter(pk=uploader_id).first()
    if uploader is None:
        return

    content_file = ContentFile(response.content, name=_filename_from_url(image_url, event_id))
    try:
        safe_save_uploaded_file(instance=event, field="cover_art", file=content_file, uploader=uploader)
    except DjangoValidationError:
        logger.info("external_ingest_cover_art_invalid", event_id=event_id, url=image_url)
