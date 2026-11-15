"""The seed files: they load, agree with each other, and hold plausible values."""

import json
import shutil

import pytest

from housing import reference
from housing.dataset import DATA_DIR, SeedError, load_seed, registered_year


@pytest.fixture(scope="module")
def seed():
    return load_seed()


@pytest.fixture
def copy(tmp_path):
    """A scratch copy of the seed files, and a way to rewrite estates.json in it."""
    for name in ("estates.json", "places.json", "context.json"):
        shutil.copy(DATA_DIR / name, tmp_path / name)

    def edit(change):
        path = tmp_path / "estates.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        change(document["estates"])
        path.write_text(json.dumps(document), encoding="utf-8")
        return tmp_path

    return edit


def test_seed_covers_the_three_garut_kecamatan_and_bandung(seed):
    assert len(seed.estates) >= 40
    assert len({estate.id for estate in seed.estates}) == len(seed.estates)
    garut = {estate.kecamatan for estate in seed.estates if estate.region == "garut"}
    assert garut == {"Leles", "Cibatu", "Wanaraja"}
    assert any(estate.region == "bandung" for estate in seed.estates)


def test_every_location_has_been_measured(seed):
    """Fails when an estate is added without re-running enrich_estates."""
    for point, estate in seed.locations():
        context = seed.context.get(point.key)
        assert context, f"{estate.desa}, {estate.kecamatan} has no measurements"
        assert set(context["access"]) == {"road", "centre", "city", "station"}
        share = context["flood"]["share"]
        assert 0 <= share["low"] + share["moderate"] + share["high"] <= 1.001


def test_every_estate_names_its_source(seed):
    for estate in seed.estates:
        assert estate.source_url == f"https://sikumbang.tapera.go.id/lokasi-perumahan/{estate.id}"
        assert estate.registered_year and 2020 <= estate.registered_year <= 2026


def test_subsidized_prices_are_plausible(seed):
    """Catches typos such as a dropped zero; none may exceed the ceiling in force."""
    for estate in seed.estates:
        for listing in estate.listings:
            if listing["subsidized"]:
                assert 100_000_000 <= listing["price_idr"] <= reference.CURRENT_CEILING_IDR, (
                    estate.name,
                    listing,
                )


def test_unit_counts_are_whole_and_not_negative(seed):
    for estate in seed.estates:
        for count in (estate.units or {}).values():
            assert count is None or (isinstance(count, int) and count >= 0), estate.name


def test_estates_without_a_site_share_their_village_point(seed):
    margaluyu = [e for e in seed.estates if (e.kecamatan, e.desa) == ("Leles", "Margaluyu")]
    assert len(margaluyu) >= 4
    assert len({estate.location.key for estate in margaluyu}) == 1
    assert {estate.precision for estate in margaluyu} == {"desa"}


@pytest.mark.parametrize(
    ("source_id", "year"),
    [
        ("GRT0920062024T002", 2024),
        ("SOR3210032021T002", 2021),
        ("NPH0820102020T001", 2020),
        ("x", None),
    ],
)
def test_registered_year_is_read_from_the_id(source_id, year):
    assert registered_year(source_id) == year


def test_an_estate_with_its_own_location_is_exact(copy):
    def give_site(estates):
        estates[0]["location"] = {"lon": 107.905, "lat": -7.101}

    first = load_seed(copy(give_site)).estates[0]
    assert first.precision == "exact"
    assert first.location.key == "107.90500,-7.10100"


def test_duplicate_ids_are_refused(copy):
    with pytest.raises(SeedError, match="listed twice"):
        load_seed(copy(lambda estates: estates.append(dict(estates[0]))))


def test_an_unknown_village_is_refused(copy):
    def move(estates):
        estates[0]["desa"] = "Antah Berantah"

    with pytest.raises(SeedError, match="no point for desa"):
        load_seed(copy(move))


def test_a_listing_without_a_price_is_refused(copy):
    def unprice(estates):
        estates[0]["listings"][0]["price_idr"] = None

    with pytest.raises(SeedError, match="needs a price"):
        load_seed(copy(unprice))
