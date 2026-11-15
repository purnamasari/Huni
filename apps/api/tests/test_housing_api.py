"""Import and API end to end, on the real seed."""

import json

import pytest

from housing.dataset import load_seed
from housing.importer import import_seed
from housing.management.commands.export_estates import DEFAULT_OUT, snapshot
from housing.models import Estate


@pytest.fixture
def seed():
    return load_seed()


@pytest.fixture
def imported(seed, db):
    return import_seed(seed)


def test_import_loads_every_estate_with_its_house_types(seed, imported):
    assert imported["estates"] == len(seed.estates) == Estate.objects.count()
    assert imported["without_context"] == 0

    ridwan = Estate.objects.get(source_id="GRT0920062024T002")
    assert ridwan.slug == "ridwan-regency-leles"
    assert (ridwan.kecamatan, ridwan.desa) == ("Leles", "Cangkuang")
    assert ridwan.registered_year == 2024
    assert (ridwan.subsidized_available, ridwan.subsidized_sold) == (49, 159)
    assert ridwan.location.srid == 4326
    assert ridwan.location.coords == pytest.approx((107.91117, -7.10312))
    assert ridwan.access["road"]["distance_m"] > 0
    (listing,) = ridwan.listings.all()
    assert (listing.name, listing.price_idr, listing.building_m2, listing.land_m2) == (
        "Tipe 34",
        166_000_000,
        34,
        60,
    )


def test_import_twice_changes_nothing_and_drops_what_left_the_seed(seed, imported):
    Estate.objects.create(
        source_id="OLD0000000000T001",
        slug="gone",
        name="Gone",
        region="garut",
        kabupaten="Kabupaten Garut",
        kecamatan="Leles",
        desa="Leles",
        location="SRID=4326;POINT(107.9 -7.1)",
        location_precision="desa",
        source_url="https://example.org",
        retrieved="2026-01-01",
    )

    again = import_seed(seed)

    assert again["estates"] == len(seed.estates) == Estate.objects.count()
    assert again["removed"] == 1
    assert again["listings"] == imported["listings"]


def test_slugs_are_unique_even_for_estates_sharing_a_name(imported):
    slugs = list(Estate.objects.values_list("slug", flat=True))
    assert len(set(slugs)) == len(slugs)


def test_list_returns_estates_with_ratings_and_dataset_meta(client, seed, imported):
    body = client.get("/api/estates").json()

    assert len(body["estates"]) == len(seed.estates)
    meta = body["meta"]
    assert meta["estate_count"] == len(seed.estates)
    assert meta["retrieved"] == seed.meta["retrieved"]
    assert [region["id"] for region in meta["regions"]] == ["garut", "bandung"]
    garut = meta["regions"][0]
    assert [k["name"] for k in garut["kecamatan"]] == ["Cibatu", "Leles", "Wanaraja"]
    assert sum(k["estate_count"] for k in garut["kecamatan"]) == garut["estate_count"]
    west, south, east, north = garut["bbox"]
    assert west < east and south < north
    assert meta["price_ceilings"][0]["price_idr"] == 166_000_000
    assert meta["kpr"]["annual_rate"] == 0.05
    assert set(meta["method"]) == {"access", "flood", "occupancy", "construction"}

    ridwan = next(e for e in body["estates"] if e["id"] == "ridwan-regency-leles")
    assert ridwan["location_precision"] == "desa"
    assert (ridwan["price_from_idr"], ridwan["price_to_idr"]) == (166_000_000, 166_000_000)
    assert ridwan["units"]["subsidized_sold"] == 159
    assert ridwan["source_url"].endswith("/GRT0920062024T002")
    assert ridwan["distance_m"] is None
    ratings = ridwan["ratings"]
    assert set(ratings) == {"access", "flood", "occupancy", "construction", "overall"}
    for key in ("access", "flood", "occupancy", "construction"):
        assert ratings[key]["level"] in (1, 2, 3, 4, 5)
    assert ratings["occupancy"] == {"level": 4, "sold": 159, "total": 208, "share": 0.764}
    assert 1 <= ratings["overall"] <= 5


def test_an_estate_with_unread_counts_is_left_unrated_not_guessed(client, imported):
    body = client.get("/api/estates/griya-rengganis").json()

    assert body["units"] is None
    assert body["listings"] == []
    assert body["price_from_idr"] is None
    assert body["ratings"]["occupancy"] == {"level": None}
    assert body["ratings"]["construction"] == {"level": None}
    # Access and flood come from the location, so they are still rated.
    assert body["ratings"]["access"]["level"] is not None
    assert body["caveats"]


def test_filters(client, seed, imported):
    def names(query: str) -> list[str]:
        return [estate["name"] for estate in client.get(f"/api/estates?{query}").json()["estates"]]

    garut = names("region=garut")
    assert len(garut) == sum(1 for e in seed.estates if e.region == "garut")

    leles = names("kecamatan=leles")
    assert "Tamaland" in leles and "Aulia Wanaraja" not in leles

    assert names("q=tamaland") == ["Tamaland", "Tamaland Cipedes"]

    in_stock = names("in_stock=true")
    assert "Tamaland" in in_stock
    assert "Bunar Indah" not in in_stock  # sold out
    assert "Griya Rengganis" not in in_stock  # counts unknown

    assert client.get("/api/estates?region=jakarta").status_code == 422


def test_near_sorts_by_distance_in_metres(client, imported):
    # Leles station.
    body = client.get("/api/estates?near=107.8998,-7.0844").json()

    distances = [estate["distance_m"] for estate in body["estates"]]
    assert distances == sorted(distances)
    nearest = body["estates"][0]
    assert nearest["kecamatan"] == "Leles"
    # Desa Kandangmukti's point is about 2.4 km from the station.
    assert nearest["desa"] == "Kandangmukti"
    assert nearest["distance_m"] == pytest.approx(2_400, rel=0.05)
    assert body["estates"][-1]["region"] == "bandung"


def test_a_malformed_near_is_ignored(client, imported):
    body = client.get("/api/estates?near=here").json()
    assert all(estate["distance_m"] is None for estate in body["estates"])


def test_detail_and_missing(client, imported):
    response = client.get("/api/estates/tamaland")
    assert response.status_code == 200
    assert response.json()["source_id"] == "GRT0920092025T001"
    assert client.get("/api/estates/does-not-exist").status_code == 404


def test_the_bundled_snapshot_matches_the_seed(imported):
    """The web app's offline copy must be what the API would serve.

    If this fails, run `manage.py import_estates` then `manage.py export_estates`.
    """
    saved = json.loads(DEFAULT_OUT.read_text(encoding="utf-8"))
    assert saved == snapshot()
