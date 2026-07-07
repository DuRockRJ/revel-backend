from django.db import models

from common.models import TimeStampedModel


class Band(TimeStampedModel):
    """A band/artist that can be lined up on one or more events."""

    name = models.CharField(max_length=64, unique=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
