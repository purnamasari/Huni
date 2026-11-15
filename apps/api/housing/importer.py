"""Load the seed dataset into the database, replacing what is there."""

from datetime import date

from django.contrib.gis.geos import Point
from django.db import transaction
from django.utils.text import slugify

from housing.dataset import Seed
from housing.models import Estate, Listing


def _slugs(seed: Seed) -> dict[str, str]:
    """A URL name per estate: its name, plus the village and then the ID when names clash."""
    by_name: dict[str, list] = {}
    for estate in seed.estates:
        by_name.setdefault(slugify(estate.name), []).append(estate)
    slugs: dict[str, str] = {}
    for base, group in by_name.items():
        for estate in group:
            if len(group) == 1:
                slugs[estate.id] = base
            else:
                slugs[estate.id] = f"{base}-{slugify(estate.desa)}-{estate.id[-8:].lower()}"
    return slugs


@transaction.atomic
def import_seed(seed: Seed) -> dict:
    """Upsert every estate by its Sikumbang ID and drop the ones no longer in the seed."""
    retrieved = date.fromisoformat(seed.meta["retrieved"])
    slugs = _slugs(seed)
    kept = []
    for row in seed.estates:
        context = seed.context.get(row.location.key, {})
        units = row.units or {}
        estate, _ = Estate.objects.update_or_create(
            source_id=row.id,
            defaults={
                "slug": slugs[row.id],
                "name": row.name,
                "developer": row.developer or "",
                "association": row.association or "",
                "region": row.region,
                "kabupaten": row.kabupaten,
                "kecamatan": row.kecamatan,
                "desa": row.desa,
                "address": row.address,
                "location": Point(row.location.lon, row.location.lat, srid=4326),
                "location_precision": row.precision,
                "registered_year": row.registered_year,
                "subsidized_available": units.get("subsidized_available"),
                "subsidized_sold": units.get("subsidized_sold"),
                "commercial_available": units.get("commercial_available"),
                "commercial_sold": units.get("commercial_sold"),
                "access": context.get("access"),
                "flood": context.get("flood"),
                "survey": row.survey,
                "caveats": row.caveats,
                "source_url": row.source_url,
                "retrieved": retrieved,
            },
        )
        kept.append(estate.pk)
        estate.listings.all().delete()
        Listing.objects.bulk_create(
            Listing(
                estate=estate,
                position=position,
                name=listing["name"],
                subsidized=listing["subsidized"],
                price_idr=listing["price_idr"],
                building_m2=listing.get("building_m2"),
                land_m2=listing.get("land_m2"),
                bedrooms=listing.get("bedrooms"),
                bathrooms=listing.get("bathrooms"),
                specs=listing.get("specs", ""),
            )
            for position, listing in enumerate(row.listings)
        )
    stale = Estate.objects.exclude(pk__in=kept)
    removed = stale.count()
    stale.delete()
    return {
        "estates": len(kept),
        "listings": Listing.objects.count(),
        "removed": removed,
        "without_context": sum(1 for e in seed.estates if e.location.key not in seed.context),
    }
