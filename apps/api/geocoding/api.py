from typing import Literal

from ninja import Query, Router, Schema, Status

from geocoding import providers

router = Router(tags=["geocoding"])


class GeocodeOut(Schema):
    id: str
    name: str
    kind: str
    context: str
    address: str
    lon: float
    lat: float
    source: str


class Unavailable(Schema):
    detail: str


@router.get("", response={200: list[GeocodeOut], 503: Unavailable})
def search(
    request,
    q: str = Query(..., min_length=3, max_length=200),
    limit: int = 6,
    source: Literal["mapbox", "photon"] | None = None,
):
    """Addresses, streets and named places in Bandung Raya matching q.

    Without `source`, results from every configured provider are merged. With it, only that
    provider is asked, so a client can show each one's results as soon as they arrive.
    """
    try:
        return providers.search(q, max(1, min(limit, 10)), source)
    except providers.GeocoderError:
        return Status(503, Unavailable(detail="Address search is unavailable right now."))


@router.get("/reverse", response={200: GeocodeOut, 404: Unavailable, 503: Unavailable})
def reverse(
    request,
    lon: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
):
    """The nearest address or named place to a point, e.g. to name a dropped pin."""
    try:
        result = providers.reverse(lon, lat)
    except providers.GeocoderError:
        return Status(503, Unavailable(detail="Address search is unavailable right now."))
    if result is None:
        return Status(404, Unavailable(detail="Nothing found here."))
    return result
