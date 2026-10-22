from django.db import DatabaseError, connection
from ninja import NinjaAPI, Schema, Status

api = NinjaAPI(title="Huni API", version="0.1.0")


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
