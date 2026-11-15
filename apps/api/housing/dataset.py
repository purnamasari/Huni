"""The seed dataset, as three JSON files in housing/data.

- estates.json: what Sikumbang says about each estate (hand-maintained, see data/README.md).
- places.json: reference points from OpenStreetMap: desa, kecamatan centres, city centres.
- context.json: what `manage.py enrich_estates` measured around each location (roads,
  stations, flood hazard). Generated, but committed so imports and tests need no network.

The files are the source of truth; the database is loaded from them by `import_estates`.
Everything here is plain Python, so it works without Django or a database.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

SOURCE_URL = "https://sikumbang.tapera.go.id/lokasi-perumahan/{id}"

REGIONS = {"garut": "Garut", "bandung": "Bandung Raya"}

# Kabupaten code, kecamatan, desa (1 = kelurahan, 2 = desa), year registered, sequence.
_SOURCE_ID = re.compile(r"^[A-Z]{3}\d{2}[12]\d{3}(\d{4})[A-Z]\d{3}$")


class SeedError(ValueError):
    """The seed files contradict each other or are missing something."""


@dataclass(frozen=True)
class Point:
    lon: float
    lat: float

    @property
    def key(self) -> str:
        """Identifies a location in context.json; five decimals is about one metre."""
        return f"{self.lon:.5f},{self.lat:.5f}"


@dataclass
class SeedEstate:
    id: str
    name: str
    region: str
    kabupaten: str
    kecamatan: str
    desa: str
    location: Point
    # "exact": the estate's own site. "desa": only the village is known, so the point is the
    # village's reference point and every estate in that village shares it.
    precision: str
    developer: str | None = None
    association: str | None = None
    address: str = ""
    units: dict | None = None
    listings: list[dict] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    # Ratings checked on site, which replace the estimates: {"occupancy": {"level": 4, ...}}.
    survey: dict = field(default_factory=dict)

    @property
    def source_url(self) -> str:
        return SOURCE_URL.format(id=self.id)

    @property
    def registered_year(self) -> int | None:
        return registered_year(self.id)


@dataclass
class Seed:
    meta: dict
    estates: list[SeedEstate]
    places: dict
    # Location key -> {"access": {...}, "flood": {...}}; empty until enrich_estates has run.
    context: dict[str, dict]

    def locations(self) -> list[tuple[Point, SeedEstate]]:
        """Each distinct location with one estate there (for its region and kecamatan)."""
        seen: dict[str, tuple[Point, SeedEstate]] = {}
        for estate in self.estates:
            seen.setdefault(estate.location.key, (estate.location, estate))
        return list(seen.values())

    def kecamatan_centre(self, estate: SeedEstate) -> dict:
        for row in self.places["kecamatan"]:
            if (row["kabupaten"], row["name"]) == (estate.kabupaten, estate.kecamatan):
                return row
        raise SeedError(f"places.json has no centre for kecamatan {estate.kecamatan}")

    def city(self, estate: SeedEstate) -> dict:
        return self.places["cities"][estate.region]


def registered_year(source_id: str) -> int | None:
    """The year an estate was registered on Sikumbang, which its ID carries."""
    match = _SOURCE_ID.match(source_id)
    return int(match.group(1)) if match else None


def _read(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def load_seed(data_dir: Path = DATA_DIR) -> Seed:
    raw = _read(data_dir / "estates.json")
    places = _read(data_dir / "places.json")
    context_path = data_dir / "context.json"
    context = _read(context_path)["locations"] if context_path.exists() else {}

    desa_points = {
        (row["kabupaten"], row["kecamatan"], row["name"]): Point(row["lon"], row["lat"])
        for row in places["desa"]
    }
    estates: list[SeedEstate] = []
    seen: set[str] = set()
    for row in raw["estates"]:
        source_id = row["id"]
        if source_id in seen:
            raise SeedError(f"{source_id} is listed twice")
        seen.add(source_id)
        if row["region"] not in REGIONS:
            raise SeedError(f"{source_id}: unknown region {row['region']!r}")

        own = row.get("location")
        if own:
            location, precision = Point(own["lon"], own["lat"]), own.get("precision", "exact")
        else:
            key = (row["kabupaten"], row["kecamatan"], row["desa"])
            if key not in desa_points:
                raise SeedError(f"{source_id}: places.json has no point for desa {key}")
            location, precision = desa_points[key], "desa"

        for listing in row.get("listings", []):
            if not isinstance(listing.get("price_idr"), int) or listing["price_idr"] <= 0:
                raise SeedError(f"{source_id}: listing {listing.get('name')!r} needs a price")

        estates.append(
            SeedEstate(
                id=source_id,
                name=row["name"],
                region=row["region"],
                kabupaten=row["kabupaten"],
                kecamatan=row["kecamatan"],
                desa=row["desa"],
                location=location,
                precision=precision,
                developer=row.get("developer"),
                association=row.get("association"),
                address=row.get("address", ""),
                units=row.get("units"),
                listings=row.get("listings", []),
                caveats=row.get("caveats", []),
                survey=row.get("survey", {}),
            )
        )
    return Seed(meta=raw["meta"], estates=estates, places=places, context=context)
