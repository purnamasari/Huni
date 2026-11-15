"""The four ratings, each from 1 (worst) to 5 (best), with the numbers behind it.

Every function takes what is known and returns a dict that always has "level" (None when
there is nothing to rate) next to its inputs, so the web app can show why an estate got
its rating. The thresholds are judgement calls, kept together here so they are easy to
question and change; docs/notes/0002 explains them.

Higher is always better: 5 for access means easy to reach, 5 for flood means outside every
mapped hazard zone.
"""

from dataclasses import dataclass

CRITERIA = ("access", "flood", "occupancy", "construction")


def _level(score: float) -> int:
    """0–100 to 1–5 in equal steps: 0–19 is 1, 20–39 is 2, ... 80–100 is 5."""
    return min(5, max(1, int(score // 20) + 1))


# --- Access ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AccessPart:
    weight: float
    # Straight-line metres: full marks up to `full_m`, none from `zero_m`, linear between.
    full_m: float
    zero_m: float


ACCESS_PARTS = {
    # The nearest trunk, primary or secondary road: where angkot, buses and ojek run.
    "road": AccessPart(weight=0.40, full_m=200, zero_m=2_500),
    # The kecamatan centre: market, puskesmas, schools, the kecamatan office.
    "centre": AccessPart(weight=0.25, full_m=500, zero_m=6_000),
    # The city the area looks to for work and bigger services.
    "city": AccessPart(weight=0.20, full_m=3_000, zero_m=25_000),
    # The nearest railway station.
    "station": AccessPart(weight=0.15, full_m=500, zero_m=6_000),
}


def closeness(distance_m: float | None, part: AccessPart) -> float:
    """0–100: how close something is, on the part's own scale. Nothing found scores 0."""
    if distance_m is None:
        return 0.0
    if distance_m <= part.full_m:
        return 100.0
    if distance_m >= part.zero_m:
        return 0.0
    return 100.0 * (part.zero_m - distance_m) / (part.zero_m - part.full_m)


def access_rating(access: dict | None) -> dict:
    """From straight-line distances to a main road, the kecamatan centre, the city, a station.

    `access` is what the enrichment measured: {"road": {"distance_m": ..., "name": ...}, ...},
    with None for a part that was not found within the search radius.
    """
    if not access:
        return {"level": None}
    score = 0.0
    parts = {}
    for key, part in ACCESS_PARTS.items():
        found = access.get(key)
        points = closeness(found["distance_m"] if found else None, part)
        score += part.weight * points
        parts[key] = {**found, "score": round(points)} if found else None
    return {"level": _level(score), "score": round(score), **parts}


# --- Flood ----------------------------------------------------------------------------

# BNPB's hazard index runs 0–1: up to 1/3 is low, up to 2/3 moderate, above that high.
FLOOD_CLASS_BOUNDS = (1 / 3, 2 / 3)

# Exposure (see flood_rating) at or below each bound earns the level; anything above is 1.
FLOOD_LEVELS = ((0.0, 5), (0.10, 4), (0.30, 3), (0.55, 2))


def hazard_class(index: float | None) -> str | None:
    if index is None or index <= 0:
        return None
    low, moderate = FLOOD_CLASS_BOUNDS
    return "low" if index <= low else "moderate" if index <= moderate else "high"


def flood_rating(flood: dict | None) -> dict:
    """From the share of the surroundings inside BNPB's mapped flood hazard zones.

    `flood` holds, for sample points spread over a disc around the location, the share in
    each hazard class (the worse of river flood and flash flood at each point). Exposure
    weighs those shares: low counts a third, moderate two thirds, high in full. So 0 means
    no sample point is in any mapped zone and 1 means all of them are in a high-hazard one.
    """
    if not flood:
        return {"level": None}
    share = flood["share"]
    exposure = share["low"] / 3 + share["moderate"] * 2 / 3 + share["high"]
    level = next((lvl for bound, lvl in FLOOD_LEVELS if exposure <= bound), 1)
    return {
        "level": level,
        "exposure": round(exposure, 3),
        "hazard_share": round(share["low"] + share["moderate"] + share["high"], 3),
        "max_class": hazard_class(flood.get("max_index")),
        **flood,
    }


# --- Occupancy and construction -------------------------------------------------------

# Share of units sold at or above each bound earns the level; below the last one is 1.
OCCUPANCY_LEVELS = ((0.90, 5), (0.70, 4), (0.40, 3), (0.10, 2))
CONSTRUCTION_LEVELS = ((0.95, 5), (0.60, 4), (0.20, 3))


def sold_share(units: dict | None) -> dict | None:
    """Units sold out of all units on record, subsidized and commercial together.

    Sikumbang counts units still for sale and units sold. None when either subsidized
    count is missing; a missing commercial count is taken as zero.
    """
    if not units:
        return None
    available, sold = units.get("subsidized_available"), units.get("subsidized_sold")
    if available is None or sold is None:
        return None
    available += units.get("commercial_available") or 0
    sold += units.get("commercial_sold") or 0
    total = available + sold
    if total == 0:
        return None
    return {"sold": sold, "total": total, "share": round(sold / total, 3)}


def occupancy_rating(units: dict | None) -> dict:
    """How lived-in the estate is, estimated from the share of units sold.

    A subsidized unit must be lived in by its buyer, so sold units are a fair stand-in for
    occupied ones. It is still sales data, not a headcount: check on site.
    """
    counts = sold_share(units)
    if counts is None:
        return {"level": None}
    level = next((lvl for bound, lvl in OCCUPANCY_LEVELS if counts["share"] >= bound), 1)
    return {"level": level, **counts}


def construction_rating(units: dict | None) -> dict:
    """How far the estate is built, estimated from the share of units handed over.

    A subsidized mortgage can only be signed for a house that is ready to live in, so every
    sold unit is a finished one: the share sold is the least that has been built. Units
    still for sale may be finished, under construction or bare plots; the counts don't say.
    """
    counts = sold_share(units)
    if counts is None:
        return {"level": None}
    if counts["sold"] == 0:
        level = 1
    else:
        level = next((lvl for bound, lvl in CONSTRUCTION_LEVELS if counts["share"] >= bound), 2)
    return {"level": level, **counts}


# --- Together -------------------------------------------------------------------------


def rate(*, access: dict | None, flood: dict | None, units: dict | None, survey: dict) -> dict:
    """All four ratings for one estate, plus their mean as "overall".

    A rating checked on site (`survey`) replaces the estimate's level; the estimate stays
    alongside as "estimated_level" so the difference is visible.
    """
    ratings = {
        "access": access_rating(access),
        "flood": flood_rating(flood),
        "occupancy": occupancy_rating(units),
        "construction": construction_rating(units),
    }
    for key, checked in (survey or {}).items():
        if key in ratings and checked.get("level") in (1, 2, 3, 4, 5):
            ratings[key] = {
                **ratings[key],
                "estimated_level": ratings[key]["level"],
                "level": checked["level"],
                "survey": {k: v for k, v in checked.items() if k != "level"},
            }
    ratings["overall"] = overall(ratings)
    return ratings


def overall(ratings: dict, criteria: tuple[str, ...] = CRITERIA) -> float | None:
    """The mean of the rated criteria, to one decimal; None when none could be rated."""
    levels = [ratings[key]["level"] for key in criteria if ratings[key]["level"] is not None]
    return round(sum(levels) / len(levels), 1) if levels else None
