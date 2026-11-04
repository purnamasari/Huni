"""Extract: read the route shapefiles and KML files into plain Python objects.

Both deliveries describe the same routes, one file per route direction:

- Shapefiles: one row per OSM way the route uses, with OSM tags (name, highway, oneway) and
  route_name/color/source. Rows are not in travel order.
- KML: one LineString placemark per way (also not in travel order) plus Point placemarks for
  terminals and, for bus and rail lines, the stops/stations.

Coordinates stay as delivered (lon, lat in EPSG:4326) here; transform.py projects them.
"""

import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString

KML_NS = "{http://www.opengis.net/kml/2.2}"

LonLat = tuple[float, float]


@dataclass
class RawPiece:
    coords: list[LonLat]
    name: str = ""
    highway: str = ""
    oneway: str = ""
    osm_way_id: int | None = None


@dataclass
class RawPoint:
    name: str
    lon: float
    lat: float


@dataclass
class RawRoute:
    name: str
    source: str = ""
    color: str | None = None
    files: list[str] = field(default_factory=list)
    pieces: list[RawPiece] = field(default_factory=list)
    points: list[RawPoint] = field(default_factory=list)
    pieces_from: str = ""


@contextmanager
def source_dir(path: Path) -> Iterator[Path]:
    """Yield a directory with the files, extracting a .zip to a temporary one first."""
    if path.is_dir():
        yield path
        return
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(path) as archive:
        archive.extractall(tmp)
        yield Path(tmp)


def _text(value) -> str:
    # Missing attributes come through as None or NaN depending on the column type.
    return "" if value is None or value != value else str(value).strip()


def _lines(geom) -> list[LineString]:
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    return []


def read_shapefiles(directory: Path) -> list[RawRoute]:
    routes = []
    for path in sorted(directory.rglob("*.shp")):
        frame = gpd.read_file(path)
        if frame.empty:
            continue
        if frame.crs is not None and frame.crs.to_epsg() != 4326:
            frame = frame.to_crs(4326)
        first = frame.iloc[0]
        route = RawRoute(
            name=_text(first.get("route_name")) or path.stem,
            source=_text(first.get("source")),
            color=_text(first.get("color")) or None,
            files=[path.name],
            pieces_from="shp",
        )
        for row in frame.itertuples(index=False):
            osm_id = _text(getattr(row, "id", None))
            for line in _lines(row.geometry):
                route.pieces.append(
                    RawPiece(
                        coords=[(x, y) for x, y, *_ in line.coords],
                        name=_text(getattr(row, "name", None)),
                        highway=_text(getattr(row, "highway", None)),
                        oneway=_text(getattr(row, "oneway", None)),
                        osm_way_id=int(float(osm_id)) if osm_id else None,
                    )
                )
        routes.append(route)
    return routes


def _kml_color(value: str | None) -> str | None:
    # KML colours are aabbggrr.
    if not value or not re.fullmatch(r"[0-9a-fA-F]{8}", value.strip()):
        return None
    value = value.strip()
    return f"#{value[6:8]}{value[4:6]}{value[2:4]}".upper()


def _coords(text: str | None) -> list[LonLat]:
    coords = []
    for chunk in (text or "").split():
        lon, lat, *_ = chunk.split(",")
        coords.append((float(lon), float(lat)))
    return coords


def read_kml_file(path: Path) -> RawRoute:
    root = ET.parse(path).getroot()
    data = {
        element.get("name"): (element.findtext(f"{KML_NS}value") or "").strip()
        for element in root.iter(f"{KML_NS}Data")
    }
    route = RawRoute(
        name=data.get("route-name") or path.stem,
        source=data.get("source", ""),
        color=_kml_color(root.findtext(f".//{KML_NS}LineStyle/{KML_NS}color")),
        files=[path.name],
        pieces_from="kml",
    )
    for placemark in root.iter(f"{KML_NS}Placemark"):
        name = (placemark.findtext(f"{KML_NS}name") or "").strip()
        point = placemark.find(f".//{KML_NS}Point/{KML_NS}coordinates")
        if point is not None:
            for lon, lat in _coords(point.text)[:1]:
                route.points.append(RawPoint(name=name, lon=lon, lat=lat))
        for line in placemark.iterfind(f".//{KML_NS}LineString/{KML_NS}coordinates"):
            coords = _coords(line.text)
            if len(coords) >= 2:
                piece_name = "" if name == "Route Segment" else name
                route.pieces.append(RawPiece(coords=coords, name=piece_name))
    return route


def read_kml(directory: Path) -> list[RawRoute]:
    return [read_kml_file(path) for path in sorted(directory.rglob("*.kml"))]


def merge(shp_routes: list[RawRoute], kml_routes: list[RawRoute]) -> list[RawRoute]:
    """One RawRoute per route name.

    Shapefile pieces win because they carry the OSM oneway tag; the KML adds the terminal and
    stop points, which the shapefiles don't have.
    """
    merged = {route.name: route for route in shp_routes}
    for kml in kml_routes:
        route = merged.get(kml.name)
        if route is None:
            merged[kml.name] = kml
            continue
        route.points = kml.points
        route.files += kml.files
        route.color = route.color or kml.color
        route.source = route.source or kml.source
    return sorted(merged.values(), key=lambda route: route.name)
