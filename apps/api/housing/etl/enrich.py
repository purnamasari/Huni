"""Measure what surrounds each location in the seed: roads, a station, the centres, flood hazard.

The result is the context document saved as housing/data/context.json, keyed by location.
Estates whose site is not known share their village's reference point, so they share its
measurements too; give an estate its own "location" in estates.json and it gets its own.

Every distance is a straight line, measured in metres in UTM zone 48S (EPSG:32748). The
eastern edge of the data (108°E) is the edge of that zone, where the projection stretches
distances by about 0.1%: a few metres on the distances that matter here.
"""

import math
from collections.abc import Callable
from datetime import date

from pyproj import Transformer
from shapely.geometry import LineString
from shapely.geometry import Point as PlanePoint
from shapely.ops import nearest_points

from housing.dataset import Point, Seed, SeedEstate
from housing.etl import mvt
from housing.etl.sources import FLASH_FLOOD, RIVER_FLOOD, Sources
from housing.ratings import hazard_class

# Zoom 12 tiles are about 9.8 km wide here and already carry every road down to tertiary,
# with vertices a couple of metres apart: enough for distances, and few tiles to fetch.
ROAD_ZOOM = 12
# Where angkot, buses and ojek run. OpenStreetMap tags national roads trunk or primary and
# provincial ones primary or secondary; tertiary (kabupaten) roads are left out.
MAIN_ROAD_CLASSES = ("trunk", "primary", "secondary")
# A little past the distances at which the access rating stops giving any credit.
ROAD_SEARCH_M = 3_500
STATION_SEARCH_M = 8_500
# Road names are complete only at the deepest zoom; a name counts when its line lies this
# close to the point on the road.
NAME_ZOOM = 14
NAME_MATCH_M = 40

# Flood hazard is sampled over a disc: one point in the middle, then rings of 6, 12, 18 and
# 24 points. Where only the village is known the disc is wide enough to take in the village.
FLOOD_RADIUS_M = {"desa": 1_000, "exact": 300}
FLOOD_RINGS = 4

_to_utm = Transformer.from_crs(4326, 32748, always_xy=True)
_to_wgs = Transformer.from_crs(32748, 4326, always_xy=True)


def distance_m(point: Point, lon: float, lat: float) -> float:
    x1, y1 = _to_utm.transform(point.lon, point.lat)
    x2, y2 = _to_utm.transform(lon, lat)
    return math.hypot(x2 - x1, y2 - y1)


def tiles_around(point: Point, radius_m: float, zoom: int) -> list[tuple[int, int]]:
    """Every tile that touches the square of this half-width around the point."""
    x, y = _to_utm.transform(point.lon, point.lat)
    west, north = _to_wgs.transform(x - radius_m, y + radius_m)
    east, south = _to_wgs.transform(x + radius_m, y - radius_m)
    x0, y0 = mvt.tile_of(west, north, zoom)
    x1, y1 = mvt.tile_of(east, south, zoom)
    return [(tx, ty) for tx in range(x0, x1 + 1) for ty in range(y0, y1 + 1)]


def _main_roads(sources: Sources, point: Point):
    """Main-road lines near a point, as (class, line in UTM metres)."""
    for tx, ty in tiles_around(point, ROAD_SEARCH_M, ROAD_ZOOM):
        features, extent = mvt.read_layer(sources.tile(ROAD_ZOOM, tx, ty), "transportation")
        for feature in features:
            road_class = feature.properties.get("class")
            if feature.type != mvt.LINE or road_class not in MAIN_ROAD_CLASSES:
                continue
            for part in feature.parts:
                if len(part) >= 2:
                    yield road_class, _line(ROAD_ZOOM, tx, ty, part, extent)


def _line(zoom: int, tx: int, ty: int, part: list, extent: int) -> LineString:
    return LineString(
        _to_utm.transform(*mvt.lonlat(zoom, tx, ty, px, py, extent)) for px, py in part
    )


def road_name(sources: Sources, lon: float, lat: float, road_class: str) -> str | None:
    """The name OpenStreetMap gives the road of this class at a point on it, if any.

    Names only reach the tiles in full at the deepest zoom, so this reads the one tile there
    that holds the point.
    """
    here = PlanePoint(*_to_utm.transform(lon, lat))
    tx, ty = mvt.tile_of(lon, lat, NAME_ZOOM)
    features, extent = mvt.read_layer(sources.tile(NAME_ZOOM, tx, ty), "transportation_name")
    best: tuple[float, str] | None = None
    for feature in features:
        name = feature.properties.get("name")
        if feature.type != mvt.LINE or not name or feature.properties.get("class") != road_class:
            continue
        for part in feature.parts:
            if len(part) < 2:
                continue
            gap = _line(NAME_ZOOM, tx, ty, part, extent).distance(here)
            if gap <= NAME_MATCH_M and (best is None or gap < best[0]):
                best = (gap, name)
    return best[1] if best else None


def nearest_road(sources: Sources, point: Point) -> dict | None:
    """The closest main road: its distance, class and (when OpenStreetMap has one) name."""
    here = PlanePoint(*_to_utm.transform(point.lon, point.lat))
    best: tuple[float, str, LineString] | None = None
    for road_class, line in _main_roads(sources, point):
        gap = line.distance(here)
        if best is None or gap < best[0]:
            best = (gap, road_class, line)
    if best is None or best[0] > ROAD_SEARCH_M:
        return None
    gap, road_class, line = best
    on_road = nearest_points(line, here)[0]
    lon, lat = _to_wgs.transform(on_road.x, on_road.y)
    return {
        "distance_m": round(gap),
        "class": road_class,
        "name": road_name(sources, lon, lat, road_class),
    }


def nearest_station(sources: Sources, point: Point) -> dict | None:
    """The closest named railway station or halt within STATION_SEARCH_M."""
    best: tuple[float, str] | None = None
    for tx, ty in tiles_around(point, STATION_SEARCH_M, ROAD_ZOOM):
        features, extent = mvt.read_layer(sources.tile(ROAD_ZOOM, tx, ty), "poi")
        for feature in features:
            name = feature.properties.get("name")
            if feature.properties.get("class") != "railway" or not name or not feature.parts:
                continue
            lon, lat = mvt.lonlat(ROAD_ZOOM, tx, ty, *feature.parts[0][0], extent)
            gap = distance_m(point, lon, lat)
            if gap <= STATION_SEARCH_M and (best is None or gap < best[0]):
                best = (gap, name)
    return {"distance_m": round(best[0]), "name": best[1]} if best else None


def flood_sample_points(point: Point, radius_m: float) -> list[tuple[float, float]]:
    """Lon/lat points spread evenly over a disc: the centre, then FLOOD_RINGS rings."""
    x, y = _to_utm.transform(point.lon, point.lat)
    plane = [(x, y)]
    for ring in range(1, FLOOD_RINGS + 1):
        count = 6 * ring
        reach = radius_m * ring / FLOOD_RINGS
        plane += [
            (
                x + reach * math.cos(2 * math.pi * i / count),
                y + reach * math.sin(2 * math.pi * i / count),
            )
            for i in range(count)
        ]
    return [tuple(round(v, 6) for v in _to_wgs.transform(px, py)) for px, py in plane]


def flood_stats(sources: Sources, point: Point, precision: str) -> dict:
    """How much of the disc around a point lies in BNPB's flood hazard zones, and how badly.

    Each sample point takes the worse of the river-flood and flash-flood indices.
    """
    radius_m = FLOOD_RADIUS_M[precision]
    points = flood_sample_points(point, radius_m)
    river = sources.hazard(RIVER_FLOOD, points)
    flash = sources.hazard(FLASH_FLOOD, points)
    worst = [
        max((v for v in pair if v is not None), default=None)
        for pair in zip(river, flash, strict=True)
    ]
    classes = [hazard_class(value) for value in worst]
    indices = [value for value in worst if value]
    count = len(points)

    def share(values: list, wanted=None) -> float:
        hits = sum(1 for v in values if (v == wanted if wanted else v))
        return round(hits / count, 3)

    return {
        "radius_m": radius_m,
        "samples": count,
        "share": {name: share(classes, name) for name in ("low", "moderate", "high")},
        "max_index": round(max(indices), 3) if indices else None,
        "river_share": share(river),
        "flash_share": share(flash),
    }


def measure(sources: Sources, seed: Seed, point: Point, estate: SeedEstate) -> dict:
    """Everything measured around one location. `estate` says which kecamatan and city apply."""
    centre, city = seed.kecamatan_centre(estate), seed.city(estate)
    return {
        "access": {
            "road": nearest_road(sources, point),
            "centre": {
                "distance_m": round(distance_m(point, centre["lon"], centre["lat"])),
                "name": centre["name"],
            },
            "city": {
                "distance_m": round(distance_m(point, city["lon"], city["lat"])),
                "name": city["name"],
            },
            "station": nearest_station(sources, point),
        },
        "flood": flood_stats(sources, point, estate.precision),
    }


def enrich(
    seed: Seed,
    sources: Sources,
    log: Callable[[str], None] = print,
    only_missing: bool = False,
) -> dict:
    """The context document for every location in the seed."""
    locations = {}
    for point, estate in seed.locations():
        if only_missing and point.key in seed.context:
            locations[point.key] = seed.context[point.key]
            continue
        locations[point.key] = measure(sources, seed, point, estate)
        access, flood = locations[point.key]["access"], locations[point.key]["flood"]
        road = access["road"]
        log(
            f"{estate.desa}, {estate.kecamatan}: "
            f"road {road['distance_m'] if road else '-'} m, "
            f"flood {flood['share']} max {flood['max_index']}"
        )
    return {
        "generated": date.today().isoformat(),
        "sources": {
            "roads_and_stations": (
                "OpenStreetMap via OpenFreeMap vector tiles "
                f"(planet {sources.tile_version()}); © OpenStreetMap contributors"
            ),
            "flood": f"BNPB inaRISK: {RIVER_FLOOD} and {FLASH_FLOOD}, 100 m rasters",
        },
        "locations": dict(sorted(locations.items())),
    }
