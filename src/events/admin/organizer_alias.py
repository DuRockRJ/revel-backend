"""Admin for OrganizerAlias."""

from django.contrib import admin
from unfold.admin import ModelAdmin

from events import models


@admin.register(models.OrganizerAlias)
class OrganizerAliasAdmin(ModelAdmin):  # type: ignore[misc]
    """Admin for mapping scraper raw organizer text to an Organization."""

    list_display = ("raw_name", "organization", "created_at")
    search_fields = ("raw_name", "organization__name")
    autocomplete_fields = ("organization",)
    ordering = ("raw_name",)
