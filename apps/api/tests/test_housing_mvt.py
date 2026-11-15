"""The vector tile reader, against tiles written by the test helper."""

import pytest

from housing.etl import mvt
from tests.housing_fixtures import encode_tile


def test_reads_lines_points_and_properties():
    tile = encode_tile(
        {
            "transportation": [
                (mvt.LINE, {"class": "primary"}, [[(0, 0), (100, 0), (100, 250)]]),
                (
                    mvt.LINE,
                    {"class": "minor"},
                    [[(10, 10), (20, 20)], [(4000, 4000), (4096, 4090)]],
                ),
            ],
            "poi": [(mvt.POINT, {"class": "railway", "name": "Cibatu"}, [[(2048, 1024)]])],
        }
    )

    roads, extent = mvt.read_layer(tile, "transportation")
    assert extent == 4096
    assert [road.properties for road in roads] == [{"class": "primary"}, {"class": "minor"}]
    assert roads[0].type == mvt.LINE
    assert roads[0].parts == [[(0, 0), (100, 0), (100, 250)]]
    # A second part starts from where the first one ended, not from the origin.
    assert roads[1].parts == [[(10, 10), (20, 20)], [(4000, 4000), (4096, 4090)]]

    (station,), _ = mvt.read_layer(tile, "poi")
    assert station.type == mvt.POINT
    assert station.properties == {"class": "railway", "name": "Cibatu"}
    assert station.parts == [[(2048, 1024)]]


def test_coordinates_outside_the_tile_survive():
    # Lines are clipped a little beyond the tile edge, so coordinates can be negative.
    tile = encode_tile(
        {"transportation": [(mvt.LINE, {"class": "trunk"}, [[(-64, 30), (4160, 30)]])]}
    )
    (road,), _ = mvt.read_layer(tile, "transportation")
    assert road.parts == [[(-64, 30), (4160, 30)]]


def test_polygon_rings_are_closed():
    tile = encode_tile({"water": [(mvt.POLYGON, {"class": "lake"}, [[(0, 0), (10, 0), (10, 10)]])]})
    (lake,), _ = mvt.read_layer(tile, "water")
    assert lake.parts == [[(0, 0), (10, 0), (10, 10), (0, 0)]]


def test_a_missing_layer_or_an_empty_tile_reads_as_nothing():
    tile = encode_tile({"poi": []})
    assert mvt.read_layer(tile, "transportation") == ([], 4096)
    assert mvt.read_layer(b"", "transportation") == ([], 4096)


def test_tile_of_and_lonlat_agree():
    lon, lat = 107.91178, -7.11624  # Desa Margaluyu, Leles
    x, y = mvt.tile_of(lon, lat, 12)
    assert (x, y) == (3275, 2129)

    west, north = mvt.lonlat(12, x, y, 0, 0, 4096)
    east, south = mvt.lonlat(12, x, y, 4096, 4096, 4096)
    assert west < lon < east
    assert south < lat < north
    # A zoom-12 tile is 360/4096 degrees wide, and its middle is half way across.
    assert east - west == pytest.approx(360 / 4096)
    assert mvt.lonlat(12, x, y, 2048, 0, 4096)[0] == pytest.approx((west + east) / 2)
