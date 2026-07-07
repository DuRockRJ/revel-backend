# src/events/admin/band.py
"""Admin classes for Band."""

from django.contrib import admin
from unfold.admin import ModelAdmin

from events import models


@admin.register(models.Band)
class BandAdmin(ModelAdmin):  # type: ignore[misc]
    """Admin for Band model."""

    list_display = ["name", "created_at"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["name"]
