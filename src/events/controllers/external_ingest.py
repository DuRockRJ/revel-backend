from django.http import HttpRequest
from ninja_extra import api_controller, route

from common.authentication import ExternalIngestAuth
from events import schema
from events.service import external_ingest_service


@api_controller("/external", auth=ExternalIngestAuth(), tags=["External Ingestion"])
class ExternalIngestController:
    @route.post("/events", url_name="ingest_events", response={200: schema.EventIngestResponseSchema})
    def ingest_events(
        self, request: HttpRequest, payload: list[schema.EventIngestSchema]
    ) -> tuple[int, schema.EventIngestResponseSchema]:
        """Ingest scraped events from an external source (e.g. rockfeed-rj).

        Machine-to-machine endpoint: every event is created as DRAFT for manual
        review and never touched again by re-ingestion once published. Dedup key
        is ``uid`` (mapped to ``Event.external_uid``), so resending the same
        event is a no-op update rather than a duplicate.
        """
        results = external_ingest_service.ingest_events(payload)
        return 200, schema.EventIngestResponseSchema(results=results)
