from datetime import date
from typing import Any, Literal

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.shortcuts import get_object_or_404
from ninja import Query, Router, Schema

from housing.models import Estate
from housing.payload import estate_payload, meta_payload

router = Router(tags=["estates"])


class ListingOut(Schema):
    name: str
    subsidized: bool
    price_idr: int
    building_m2: int | None
    land_m2: int | None
    bedrooms: int | None
    bathrooms: int | None
    specs: str


class EstateOut(Schema):
    id: str
    source_id: str
    name: str
    developer: str | None
    association: str | None
    region: str
    kabupaten: str
    kecamatan: str
    desa: str
    address: str
    lon: float
    lat: float
    # "exact" (the estate's site) or "desa" (the village's reference point).
    location_precision: str
    registered_year: int | None
    # Sikumbang's counters, or null when they could not be read.
    units: dict[str, int | None] | None
    price_from_idr: int | None
    price_to_idr: int | None
    listings: list[ListingOut]
    # access, flood, occupancy, construction: each {"level": 1–5 or null, ...inputs},
    # plus "overall", their mean. See housing/ratings.py.
    ratings: dict[str, Any]
    caveats: list[str]
    source_url: str
    retrieved: date
    # Straight-line metres from `near`, when it was given.
    distance_m: int | None


class EstatesOut(Schema):
    meta: dict[str, Any]
    estates: list[EstateOut]


def _point(near: str) -> Point | None:
    try:
        lon, lat = (float(part) for part in near.split(","))
    except ValueError:
        return None
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return Point(lon, lat, srid=4326)


@router.get("", response=EstatesOut)
def list_estates(
    request,
    region: Literal["garut", "bandung"] | None = None,
    kecamatan: str | None = None,
    q: str | None = Query(None, max_length=80),
    in_stock: bool = False,
    near: str | None = Query(None, description="lon,lat: sort by distance from this point"),
):
    """Subsidized housing estates with their house types, prices and ratings.

    `meta` always describes the whole dataset, whatever the filters.
    """
    everything = list(Estate.objects.all())
    estates = Estate.objects.prefetch_related("listings").in_reading_order()
    if region:
        estates = estates.filter(region=region)
    if kecamatan:
        estates = estates.filter(kecamatan__iexact=kecamatan)
    if q:
        estates = estates.filter(name__icontains=q.strip())
    if in_stock:
        estates = estates.filter(subsidized_available__gt=0)

    origin = _point(near) if near else None
    if origin:
        # A geodetic SRID, so PostGIS measures on the sphere and the result is in metres.
        estates = estates.annotate(distance=Distance("location", origin)).order_by("distance")
    return {
        "meta": meta_payload(everything),
        "estates": [
            estate_payload(estate, estate.distance.m if origin else None) for estate in estates
        ],
    }


@router.get("/{slug}", response=EstateOut)
def get_estate(request, slug: str):
    estate = get_object_or_404(Estate.objects.prefetch_related("listings"), slug=slug)
    return estate_payload(estate)
