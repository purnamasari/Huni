"""Enrichment: distances to roads and stations, and flood sampling, against known answers."""

import math

import pytest

from housing.dataset import Point
from housing.etl import enrich, mvt
from housing.etl.sources import FLASH_FLOOD, RIVER_FLOOD
from tests.housing_fixtures import FakeSources, encode_tile

# Desa Margaluyu, Leles. One tile unit at zoom 12 is about 2.37 m on the ground here.
HERE = Point(107.91178, -7.11624)
ZOOM = enrich.ROAD_ZOOM
TILE = mvt.tile_of(HERE.lon, HERE.lat, ZOOM)
EXTENT = 4096
UNIT_M = 40_075_016.686 * math.cos(math.radians(HERE.lat)) / (2**ZOOM * EXTENT)


def tile_position(point: Point) -> tuple[int, int]:
    """Where a point falls inside TILE, in tile units."""
    n = 2**ZOOM
    px = ((point.lon + 180) / 360 * n - TILE[0]) * EXTENT
    py = ((1 - math.asinh(math.tan(math.radians(point.lat))) / math.pi) / 2 * n - TILE[1]) * EXTENT
    return round(px), round(py)


def sources_with(layers: dict, **kwargs) -> FakeSources:
    return FakeSources(tiles={(ZOOM, *TILE): encode_tile(layers)}, **kwargs)


def test_distance_m_matches_a_known_distance():
    # One hundredth of a degree of latitude is about 1,106 m at this latitude.
    assert enrich.distance_m(HERE, HERE.lon, HERE.lat + 0.01) == pytest.approx(1106, rel=0.005)


def test_tiles_around_covers_the_search_square():
    tiles = enrich.tiles_around(HERE, 3_500, ZOOM)
    assert TILE in tiles
    # The point sits 3.4 km from the tile's north edge and 6.3 km from its west edge.
    assert (TILE[0], TILE[1] - 1) in tiles
    assert (TILE[0] - 1, TILE[1]) not in tiles


def test_nearest_road_ignores_small_roads_and_measures_to_the_line():
    px, py = tile_position(HERE)
    sources = sources_with(
        {
            "transportation": [
                # A village road right next to the point: not a main road.
                (mvt.LINE, {"class": "minor"}, [[(px - 50, py + 2), (px + 50, py + 2)]]),
                # An east-west primary road 200 tile units to the north.
                (mvt.LINE, {"class": "primary"}, [[(px - 800, py - 200), (px + 800, py - 200)]]),
                # A secondary road further away.
                (mvt.LINE, {"class": "secondary"}, [[(px - 800, py + 600), (px + 800, py + 600)]]),
            ]
        }
    )

    road = enrich.nearest_road(sources, HERE)

    assert road["class"] == "primary"
    assert road["distance_m"] == pytest.approx(200 * UNIT_M, rel=0.01)
    # No name tile was supplied, so the road is left unnamed rather than guessed.
    assert road["name"] is None


def test_nearest_road_takes_its_name_from_the_name_layer():
    px, py = tile_position(HERE)
    sources = sources_with(
        {"transportation": [(mvt.LINE, {"class": "primary"}, [[(px - 800, py), (px + 800, py)]])]}
    )
    # The name comes from the zoom-14 tile that holds the nearest point on the road.
    name_tile = mvt.tile_of(HERE.lon, HERE.lat, enrich.NAME_ZOOM)
    # Put the named line through the point: first, the point's position in that tile.
    n = 2**enrich.NAME_ZOOM
    nx = round(((HERE.lon + 180) / 360 * n - name_tile[0]) * EXTENT)
    ny = round(
        ((1 - math.asinh(math.tan(math.radians(HERE.lat))) / math.pi) / 2 * n - name_tile[1])
        * EXTENT
    )
    sources.tiles[(enrich.NAME_ZOOM, *name_tile)] = encode_tile(
        {
            "transportation_name": [
                (
                    mvt.LINE,
                    {"class": "minor", "name": "Gang Mawar"},
                    [[(nx - 9, ny), (nx + 9, ny)]],
                ),
                (
                    mvt.LINE,
                    {"class": "primary", "name": "Jalan Raya Leles"},
                    [[(nx - 300, ny + 3), (nx + 300, ny + 3)]],
                ),
            ]
        }
    )

    road = enrich.nearest_road(sources, HERE)

    assert road["distance_m"] <= 2
    assert road["name"] == "Jalan Raya Leles"


def test_nearest_road_is_none_when_nothing_is_within_reach():
    assert enrich.nearest_road(FakeSources(), HERE) is None

    px, py = tile_position(HERE)
    far = round(enrich.ROAD_SEARCH_M / UNIT_M) + 100
    sources = sources_with(
        {
            "transportation": [
                (mvt.LINE, {"class": "trunk"}, [[(px - 9, py - far), (px + 9, py - far)]])
            ]
        }
    )
    assert enrich.nearest_road(sources, HERE) is None


def test_nearest_station_picks_the_closest_named_one():
    px, py = tile_position(HERE)
    sources = sources_with(
        {
            "poi": [
                (mvt.POINT, {"class": "railway", "name": "Leles"}, [[(px + 1500, py)]]),
                (mvt.POINT, {"class": "railway", "name": "Karangsari"}, [[(px, py - 1000)]]),
                # Closer, but not a station, and one without a name.
                (mvt.POINT, {"class": "school", "name": "SDN 1"}, [[(px + 10, py)]]),
                (mvt.POINT, {"class": "railway"}, [[(px + 20, py)]]),
            ]
        }
    )

    station = enrich.nearest_station(sources, HERE)

    assert station["name"] == "Karangsari"
    assert station["distance_m"] == pytest.approx(1000 * UNIT_M, rel=0.01)


def test_nearest_station_is_none_beyond_the_search_radius():
    assert enrich.nearest_station(FakeSources(), HERE) is None


def test_flood_sample_points_fill_the_disc():
    points = enrich.flood_sample_points(HERE, 1_000)

    assert len(points) == 61
    assert points[0] == (HERE.lon, HERE.lat)
    distances = [enrich.distance_m(HERE, lon, lat) for lon, lat in points]
    assert max(distances) == pytest.approx(1_000, abs=1)
    # Rings at 250, 500, 750 and 1,000 m with 6, 12, 18 and 24 points.
    for ring, count in enumerate((6, 12, 18, 24), start=1):
        on_ring = [d for d in distances if d == pytest.approx(250 * ring, abs=1)]
        assert len(on_ring) == count


def test_flood_stats_take_the_worse_of_river_and_flash_flood():
    def river(lon, lat):
        # Moderate river-flood hazard over the eastern half of the disc.
        return 0.5 if lon > HERE.lon else None

    def flash(lon, lat):
        # A band of high flash-flood hazard across the north.
        return 0.9 if lat > HERE.lat + 0.005 else None

    sources = FakeSources(hazard={RIVER_FLOOD: river, FLASH_FLOOD: flash})

    stats = enrich.flood_stats(sources, HERE, "desa")

    assert stats["radius_m"] == 1_000
    assert stats["samples"] == 61
    assert stats["max_index"] == 0.9
    assert stats["share"]["low"] == 0
    # Where both apply, the point counts once, as high.
    assert stats["share"]["high"] == stats["flash_share"]
    assert stats["share"]["moderate"] < stats["river_share"]
    assert stats["share"]["moderate"] + stats["share"]["high"] == pytest.approx(
        sum(
            1
            for lon, lat in enrich.flood_sample_points(HERE, 1_000)
            if river(lon, lat) or flash(lon, lat)
        )
        / 61,
        abs=0.002,
    )


def test_flood_stats_outside_every_zone():
    stats = enrich.flood_stats(FakeSources(), HERE, "exact")

    assert stats["radius_m"] == 300
    assert stats["share"] == {"low": 0, "moderate": 0, "high": 0}
    assert stats["max_index"] is None
    assert stats["river_share"] == 0
    assert stats["flash_share"] == 0
