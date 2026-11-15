"""Turn estates into the JSON the web app reads.

GET /api/estates returns {"meta": ..., "estates": [...]} built here, and the web app's
bundled snapshot is the same document saved to a file (`manage.py export_estates`), so the
app shows the same thing with or without the API.
"""

from collections.abc import Iterable

from housing import ratings, reference
from housing.dataset import REGIONS
from housing.models import Estate


def listing_payload(listing) -> dict:
    return {
        "name": listing.name,
        "subsidized": listing.subsidized,
        "price_idr": listing.price_idr,
        "building_m2": listing.building_m2,
        "land_m2": listing.land_m2,
        "bedrooms": listing.bedrooms,
        "bathrooms": listing.bathrooms,
        "specs": listing.specs,
    }


def estate_payload(estate: Estate, distance_m: float | None = None) -> dict:
    listings = [listing_payload(listing) for listing in estate.listings.all()]
    prices = [listing["price_idr"] for listing in listings if listing["subsidized"]]
    return {
        "id": estate.slug,
        "source_id": estate.source_id,
        "name": estate.name,
        "developer": estate.developer or None,
        "association": estate.association or None,
        "region": estate.region,
        "kabupaten": estate.kabupaten,
        "kecamatan": estate.kecamatan,
        "desa": estate.desa,
        "address": estate.address,
        "lon": round(estate.location.x, 5),
        "lat": round(estate.location.y, 5),
        "location_precision": estate.location_precision,
        "registered_year": estate.registered_year,
        "units": estate.units,
        # The cheapest and dearest subsidized type; null when no type is on record.
        "price_from_idr": min(prices) if prices else None,
        "price_to_idr": max(prices) if prices else None,
        "listings": listings,
        "ratings": ratings.rate(
            access=estate.access, flood=estate.flood, units=estate.units, survey=estate.survey
        ),
        "caveats": estate.caveats,
        "source_url": estate.source_url,
        "retrieved": estate.retrieved.isoformat(),
        "distance_m": None if distance_m is None else round(distance_m),
    }


def _method() -> dict:
    """The rating thresholds, so the methodology page always states the ones in use."""
    return {
        "access": {
            key: {"weight": part.weight, "full_m": part.full_m, "zero_m": part.zero_m}
            for key, part in ratings.ACCESS_PARTS.items()
        },
        "flood": [{"max_exposure": bound, "level": level} for bound, level in ratings.FLOOD_LEVELS],
        "occupancy": [
            {"min_share": bound, "level": level} for bound, level in ratings.OCCUPANCY_LEVELS
        ],
        "construction": [
            {"min_share": bound, "level": level} for bound, level in ratings.CONSTRUCTION_LEVELS
        ],
    }


def meta_payload(estates: Iterable[Estate]) -> dict:
    """Describes the whole dataset: regions and their kecamatan, dates, programme facts."""
    estates = list(estates)
    regions = []
    for region_id, region_name in REGIONS.items():
        members = [estate for estate in estates if estate.region == region_id]
        if not members:
            continue
        kecamatan: dict[tuple[str, str], int] = {}
        for estate in members:
            key = (estate.kabupaten, estate.kecamatan)
            kecamatan[key] = kecamatan.get(key, 0) + 1
        lons = [estate.location.x for estate in members]
        lats = [estate.location.y for estate in members]
        regions.append(
            {
                "id": region_id,
                "name": region_name,
                "estate_count": len(members),
                # West, south, east, north.
                "bbox": [min(lons), min(lats), max(lons), max(lats)],
                "kecamatan": [
                    {"name": name, "kabupaten": kabupaten, "estate_count": count}
                    for (kabupaten, name), count in sorted(
                        kecamatan.items(), key=lambda item: item[0][1]
                    )
                ],
            }
        )
    return {
        "retrieved": max((estate.retrieved for estate in estates), default=None),
        "estate_count": len(estates),
        "regions": regions,
        "price_ceilings": reference.PRICE_CEILINGS,
        "kpr": reference.KPR,
        "sources": reference.SOURCES,
        "method": _method(),
    }
