"""Tests for the post_delete signal that tombstones deleted external events."""

import pytest
from django.utils import timezone

from events.models import DeletedExternalEvent, Event, Organization

pytestmark = pytest.mark.django_db


def test_delete_tombstones_event_with_external_uid(organization: Organization) -> None:
    event = Event.objects.create(
        organization=organization,
        name="Show Raspado",
        external_uid="uid-to-delete",
        start=timezone.now(),
    )

    event.delete()

    assert DeletedExternalEvent.objects.filter(external_uid="uid-to-delete").exists()


def test_delete_does_not_tombstone_event_without_external_uid(organization: Organization) -> None:
    event = Event.objects.create(organization=organization, name="Show Manual", start=timezone.now())

    event.delete()

    assert DeletedExternalEvent.objects.count() == 0


def test_bulk_queryset_delete_also_tombstones(organization: Organization) -> None:
    Event.objects.create(
        organization=organization,
        name="Show Raspado",
        external_uid="uid-bulk-delete",
        start=timezone.now(),
    )

    Event.objects.filter(external_uid="uid-bulk-delete").delete()

    assert DeletedExternalEvent.objects.filter(external_uid="uid-bulk-delete").exists()


def test_delete_is_idempotent_for_same_uid(organization: Organization) -> None:
    """Two events sharing an external_uid can't coexist (unique constraint), but
    deleting-then-recreating-then-deleting the same uid must not blow up on the
    second tombstone insert."""
    event = Event.objects.create(
        organization=organization,
        name="Show Raspado",
        external_uid="uid-repeat-delete",
        start=timezone.now(),
    )
    event.delete()
    assert DeletedExternalEvent.objects.filter(external_uid="uid-repeat-delete").count() == 1

    recreated = Event.objects.create(
        organization=organization,
        name="Show Raspado de Novo",
        external_uid="uid-repeat-delete",
        start=timezone.now(),
    )
    recreated.delete()

    assert DeletedExternalEvent.objects.filter(external_uid="uid-repeat-delete").count() == 1
