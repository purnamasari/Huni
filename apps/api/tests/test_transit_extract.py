import zipfile

import geopandas as gpd
from shapely.geometry import LineString

from tests.transit_fixtures import write_kml
from transit.etl.extract import merge, read_kml_file, read_shapefiles, source_dir


def test_read_kml_file(tmp_path):
    path = write_kml(
        tmp_path / "09_ Dago _ Stasiun Hall.kml",
        "09: Dago → Stasiun Hall",
        [[(107.62, -6.87), (107.61, -6.88)], [(107.61, -6.88), (107.60, -6.91)]],
        [("Terminal Dago", 107.6212, -6.8671)],
        color="ff295AF1",
    )

    route = read_kml_file(path)

    assert route.name == "09: Dago → Stasiun Hall"
    assert route.source == "Test fixture"
    assert route.color == "#F15A29"  # KML colours are aabbggrr
    assert [(p.name, p.lon, p.lat) for p in route.points] == [("Terminal Dago", 107.6212, -6.8671)]
    assert len(route.pieces) == 2
    assert route.pieces[0].name == ""  # "Route Segment" is a placeholder name
    assert route.pieces[1].coords == [(107.61, -6.88), (107.60, -6.91)]


def test_read_shapefiles_and_merge_with_kml(tmp_path):
    frame = gpd.GeoDataFrame(
        {
            "id": [111, 222],
            "route_name": ["09: Dago → Stasiun Hall"] * 2,
            "color": ["#F15A29"] * 2,
            "source": ["Transport for Bandung"] * 2,
            "name": ["Jalan Ir. H. Djuanda", None],
            "highway": ["primary", "secondary"],
            "oneway": [None, "yes"],
        },
        geometry=[
            LineString([(107.62, -6.87), (107.61, -6.88)]),
            LineString([(107.61, -6.88), (107.60, -6.91)]),
        ],
        crs=4326,
    )
    frame.to_file(tmp_path / "09 - Dago - Stasiun Hall.shp")
    kml = write_kml(
        tmp_path / "route.kml",
        "09: Dago → Stasiun Hall",
        [],
        [("Terminal Dago", 107.6212, -6.8671)],
    )

    (shp_route,) = read_shapefiles(tmp_path)
    assert [p.osm_way_id for p in shp_route.pieces] == [111, 222]
    assert [p.oneway for p in shp_route.pieces] == ["", "yes"]
    assert shp_route.pieces[0].name == "Jalan Ir. H. Djuanda"

    (merged,) = merge([shp_route], [read_kml_file(kml)])
    assert merged.pieces_from == "shp"
    assert len(merged.pieces) == 2
    assert [p.name for p in merged.points] == ["Terminal Dago"]
    assert merged.files == ["09 - Dago - Stasiun Hall.shp", "route.kml"]


def test_source_dir_extracts_zip(tmp_path):
    archive = tmp_path / "routes.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("a.kml", "<kml/>")

    with source_dir(archive) as directory:
        assert (directory / "a.kml").read_text() == "<kml/>"
    assert not directory.exists()
