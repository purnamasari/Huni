from django.db import DatabaseError, connection
from ninja import NinjaAPI, Schema, Status

from geocoding.api import router as geocoding_router
from transit.api import router as transit_router

api = NinjaAPI(title="Huni API", version="0.1.0")
api.add_router("/transit", transit_router)
api.add_router("/geocode", geocoding_router)


class HealthOut(Schema):
    status: str
    database: str
    postgis: str | None = None


@api.get("/health", response={200: HealthOut, 503: HealthOut})
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT postgis_lib_version()")
            (postgis,) = cursor.fetchone()
    except DatabaseError:
        return Status(503, HealthOut(status="error", database="unavailable"))
    return Status(200, HealthOut(status="ok", database="ok", postgis=postgis))
