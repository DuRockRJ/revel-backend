"""DeletedExternalEvent — tombstones for events deleted after external ingestion."""

from django.db import models

from common.models import TimeStampedModel


class DeletedExternalEvent(TimeStampedModel):
    """Records an ``external_uid`` whose Event was deleted, so it isn't re-imported.

    The Event row itself is gone after deletion (hard delete, both from the API
    and the Django admin), so ``external_ingest_service`` can't tell "never
    seen" apart from "seen and deliberately deleted" without this ledger.
    Populated by a ``post_delete`` signal on ``Event``.
    """

    external_uid = models.CharField(max_length=64, unique=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Deleted external event"
        verbose_name_plural = "Deleted external events"

    def __str__(self) -> str:
        return self.external_uid
