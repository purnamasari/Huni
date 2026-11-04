"""Small hand-made route files in the same shape as the Transport for Bandung delivery."""

from pathlib import Path

KML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Style id="line"><LineStyle><color>{color}</color><width>4</width></LineStyle></Style>
    {placemarks}
    <ExtendedData>
      <Data name="route-name"><value>{route_name}</value></Data>
      <Data name="source"><value>Test fixture</value></Data>
    </ExtendedData>
  </Document>
</kml>
"""


def _point(name: str, lon: float, lat: float) -> str:
    return (
        f"<Placemark><name>{name}</name>"
        f"<Point><coordinates>{lon},{lat},0.0</coordinates></Point></Placemark>"
    )


def _line(name: str, coords: list[tuple[float, float]]) -> str:
    text = " ".join(f"{lon},{lat},0.0" for lon, lat in coords)
    return (
        f"<Placemark><name>{name}</name><styleUrl>#line</styleUrl>"
        f"<LineString><coordinates>{text}</coordinates></LineString></Placemark>"
    )


def write_kml(
    path: Path,
    route_name: str,
    pieces: list[list[tuple[float, float]]],
    points: list[tuple[str, float, float]],
    color: str = "ff295AF1",
) -> Path:
    placemarks = [_point(*p) for p in points] + [_line("Route Segment", c) for c in pieces]
    path.write_text(
        KML_TEMPLATE.format(color=color, placemarks="\n".join(placemarks), route_name=route_name)
    )
    return path


def _split(start: tuple[float, float], end: tuple[float, float], parts: int):
    """A straight line from start to end as `parts` pieces, last piece first and reversed."""
    lons = [start[0] + (end[0] - start[0]) * i / parts for i in range(parts + 1)]
    lats = [start[1] + (end[1] - start[1]) * i / parts for i in range(parts + 1)]
    coords = list(zip(lons, lats, strict=True))
    pieces = [coords[i : i + 2] for i in range(parts)]
    return [pieces[-1][::-1], *pieces[:-1]]


# Two angkot lines crossing at roughly (107.60, -6.90): one west → east, one north → south.
WEST, EAST = (107.58, -6.90), (107.62, -6.90)
NORTH, SOUTH = (107.60, -6.88), (107.60, -6.92)


def write_network(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    write_kml(
        directory / "T1_ West _ East.kml",
        "T1: West → East",
        _split(WEST, EAST, 4),
        [("Terminal West", *WEST), ("Terminal East", *EAST)],
    )
    write_kml(
        directory / "T2_ North _ South.kml",
        "T2: North → South",
        _split(NORTH, SOUTH, 4),
        [("Terminal South", *SOUTH), ("Terminal North", *NORTH)],
        color="ff00FF00",
    )
    return directory
