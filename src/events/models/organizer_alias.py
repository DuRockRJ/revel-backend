"""OrganizerAlias — decouples the scraper's raw organizer text from Organization.name."""

from django.db import models

from common.models import TimeStampedModel

from .organization import Organization


class OrganizerAlias(TimeStampedModel):
    """Maps a scraper's raw ``organizer`` text to an Organization.

    ``external_ingest_service._resolve_organization`` checks this table before
    falling back to matching/creating by ``Organization.name`` — so renaming an
    Organization doesn't orphan the raw text that originally created it (which
    would otherwise spawn a duplicate Organization on the next scrape). New
    aliases are recorded automatically the first time a raw name resolves via
    the name-matching fallback; admins can also add or repoint them manually.
    """

    raw_name = models.CharField(max_length=255, unique=True, db_index=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="organizer_aliases")

    class Meta:
        ordering = ["raw_name"]
        verbose_name = "Organizer alias"
        verbose_name_plural = "Organizer aliases"

    def __str__(self) -> str:
        return f"{self.raw_name} -> {self.organization.name}"
