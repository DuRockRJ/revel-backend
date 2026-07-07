from django.db.models import Count, QuerySet
from ninja_extra import api_controller, route
from ninja_extra.pagination import PageNumberPaginationExtra, PaginatedResponseSchema, paginate
from ninja_extra.searching import Searching, searching

from common.controllers import UserAwareController
from events.models import Band
from events.schema import BandSchema


@api_controller("/bands", tags=["Bands"])
class BandController(UserAwareController):
    @route.get("/", url_name="list_bands", response=PaginatedResponseSchema[BandSchema])
    @paginate(PageNumberPaginationExtra, page_size=20)
    @searching(Searching, search_fields=["name"])
    def list_bands(self) -> QuerySet[Band]:
        """Browse and search all bands in the system.

        Supports autocomplete via the 'search' query parameter (e.g., /api/bands/?search=nirv).
        Use this to populate band selection dropdowns or filters. Results are ordered by
        popularity (most used first).
        """
        return Band.objects.annotate(usage_count=Count("events")).order_by("-usage_count", "name")
