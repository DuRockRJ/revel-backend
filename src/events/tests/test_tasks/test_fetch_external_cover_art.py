"""Tests for the external-ingestion cover-art fetch task."""

import typing as t
from datetime import timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch

import httpx
import pytest
from django.utils import timezone
from PIL import Image

from accounts.models import RevelUser
from events.models import Event, Organization
from events.tasks.external_ingest import fetch_external_cover_art

pytestmark = pytest.mark.django_db

IMAGE_URL = "https://files.meaple.com.br/meaple/example.jpg"


@pytest.fixture
def draft_event(organization: Organization) -> Event:
    return Event.objects.create(
        organization=organization,
        name="Show de Teste",
        start=timezone.now() + timedelta(days=5),
    )


def _ok_response(content: bytes) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.side_effect = None
    response.content = content
    return response


def _image_bytes(width: int, height: int) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color="blue").save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


class TestFetchExternalCoverArt:
    def test_downloads_and_sets_cover_art_on_success(
        self, draft_event: Event, user: RevelUser, large_image_bytes: bytes
    ) -> None:
        with patch("events.tasks.external_ingest.httpx.get", return_value=_ok_response(large_image_bytes)):
            fetch_external_cover_art(str(draft_event.id), IMAGE_URL, str(user.id))

        draft_event.refresh_from_db()
        assert draft_event.cover_art
        assert draft_event.cover_art.name.endswith(".jpg")

    def test_skips_when_event_missing(self, user: RevelUser, large_image_bytes: bytes) -> None:
        with patch("events.tasks.external_ingest.httpx.get", return_value=_ok_response(large_image_bytes)) as get:
            fetch_external_cover_art("00000000-0000-0000-0000-000000000000", IMAGE_URL, str(user.id))
        get.assert_not_called()

    def test_skips_when_event_not_draft(self, draft_event: Event, user: RevelUser, large_image_bytes: bytes) -> None:
        draft_event.status = Event.EventStatus.OPEN
        draft_event.save(update_fields=["status"])

        with patch("events.tasks.external_ingest.httpx.get", return_value=_ok_response(large_image_bytes)) as get:
            fetch_external_cover_art(str(draft_event.id), IMAGE_URL, str(user.id))
        get.assert_not_called()

    def test_skips_when_event_already_has_cover_art(
        self, draft_event: Event, user: RevelUser, large_image_bytes: bytes
    ) -> None:
        with patch("events.tasks.external_ingest.httpx.get", return_value=_ok_response(large_image_bytes)):
            fetch_external_cover_art(str(draft_event.id), IMAGE_URL, str(user.id))
        draft_event.refresh_from_db()
        first_name = draft_event.cover_art.name

        with patch("events.tasks.external_ingest.httpx.get", return_value=_ok_response(large_image_bytes)) as get:
            fetch_external_cover_art(str(draft_event.id), IMAGE_URL, str(user.id))
        get.assert_not_called()
        draft_event.refresh_from_db()
        assert draft_event.cover_art.name == first_name

    def test_skips_on_http_status_error(self, draft_event: Event, user: RevelUser) -> None:
        response = MagicMock()
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "not found", request=MagicMock(), response=MagicMock()
        )

        with patch("events.tasks.external_ingest.httpx.get", return_value=response):
            fetch_external_cover_art(str(draft_event.id), IMAGE_URL, str(user.id))

        draft_event.refresh_from_db()
        assert not draft_event.cover_art

    def test_skips_when_response_too_large(
        self, draft_event: Event, user: RevelUser, large_image_bytes: bytes, monkeypatch: t.Any
    ) -> None:
        monkeypatch.setattr("events.tasks.external_ingest.MAX_IMAGE_SIZE_BYTES", 5)

        with patch("events.tasks.external_ingest.httpx.get", return_value=_ok_response(large_image_bytes)):
            fetch_external_cover_art(str(draft_event.id), IMAGE_URL, str(user.id))

        draft_event.refresh_from_db()
        assert not draft_event.cover_art

    def test_skips_when_image_is_too_small(self, draft_event: Event, user: RevelUser, png_bytes: bytes) -> None:
        """1x1 placeholders and small square logos (166x166 etc.) don't fit as a cover photo."""
        with patch("events.tasks.external_ingest.httpx.get", return_value=_ok_response(png_bytes)):
            fetch_external_cover_art(str(draft_event.id), IMAGE_URL, str(user.id))

        draft_event.refresh_from_db()
        assert not draft_event.cover_art

    def test_accepts_portrait_poster(self, draft_event: Event, user: RevelUser) -> None:
        """A tall, narrow show flyer (common for BR events) is a valid cover, not a placeholder."""
        with patch("events.tasks.external_ingest.httpx.get", return_value=_ok_response(_image_bytes(400, 900))):
            fetch_external_cover_art(str(draft_event.id), IMAGE_URL, str(user.id))

        draft_event.refresh_from_db()
        assert draft_event.cover_art

    def test_accepts_square_image(self, draft_event: Event, user: RevelUser) -> None:
        with patch("events.tasks.external_ingest.httpx.get", return_value=_ok_response(_image_bytes(400, 400))):
            fetch_external_cover_art(str(draft_event.id), IMAGE_URL, str(user.id))

        draft_event.refresh_from_db()
        assert draft_event.cover_art

    def test_rejects_narrow_portrait_image(self, draft_event: Event, user: RevelUser) -> None:
        """Even in portrait orientation, the short side must still clear the minimum."""
        with patch("events.tasks.external_ingest.httpx.get", return_value=_ok_response(_image_bytes(100, 900))):
            fetch_external_cover_art(str(draft_event.id), IMAGE_URL, str(user.id))

        draft_event.refresh_from_db()
        assert not draft_event.cover_art

    def test_skips_when_uploader_missing(self, draft_event: Event, large_image_bytes: bytes) -> None:
        with patch("events.tasks.external_ingest.httpx.get", return_value=_ok_response(large_image_bytes)):
            fetch_external_cover_art(str(draft_event.id), IMAGE_URL, "00000000-0000-0000-0000-000000000000")

        draft_event.refresh_from_db()
        assert not draft_event.cover_art

    def test_skips_when_content_is_not_a_valid_image(self, draft_event: Event, user: RevelUser) -> None:
        with patch("events.tasks.external_ingest.httpx.get", return_value=_ok_response(b"not an image")):
            fetch_external_cover_art(str(draft_event.id), IMAGE_URL, str(user.id))

        draft_event.refresh_from_db()
        assert not draft_event.cover_art
