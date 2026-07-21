from decouple import config

EXTERNAL_INGEST_API_KEY = config("EXTERNAL_INGEST_API_KEY", default="")
