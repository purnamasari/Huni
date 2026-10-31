import pytest
from django.core.cache import cache

from geocoding.providers import GeocoderError, Mapbox, Photon


def photon_feature(osm_id, lon, lat, **properties):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"osm_type": "N", "osm_id": osm_id, "type": "house", **properties},
    }


def mapbox_feature(mapbox_id, lon, lat, **properties):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"mapbox_id": mapbox_id, "feature_type": "poi", **properties},
    }


# Shapes taken from live responses for Bandung.
CIWALK = photon_feature(
    123,
    107.6044,
    -6.8935,
    osm_type="W",
    osm_key="shop",
    name="Cihampelas Walk (CiWalk)",
    street="Jalan Cihampelas",
    housenumber="160",
    district="Cipaganti",
    city="Bandung",
)
HOUSE = photon_feature(
    7, 107.6091, -6.9175, street="Jalan Braga", housenumber="12", district="Braga", city="Bandung"
)
STREET = photon_feature(9, 107.6088, -6.9160, osm_type="W", type="street", name="Jalan Braga")
PHOTON_KOSAMBI = photon_feature(
    5, 107.6221462, -6.9198411, name="Pasar Kosambi", street="Jalan Jenderal Ahmad Yani"
)
MAPBOX_KOSAMBI = mapbox_feature(
    "abc",
    107.62215,
    -6.91985,
    name="Pasar Kosambi",
    address="Jl. A. Yani No.221-223",
    place_formatted="Bandung, 40112, Indonesia",
    context={
        "place": {"name": "Bandung"},
        "neighborhood": {"name": "Kebon Pisang"},
        "street": {"name": "Jl. A. Yani"},
    },
)
MAPBOX_KOSAMBI_1 = mapbox_feature(
    "def",
    107.6150,
    -6.9300,
    name="Pasar Kosambi 1",
    address="Bandung",  # Mapbox puts the city here when it has no street
    place_formatted="40262, Indonesia",
    context={"place": {"name": "Bandung"}, "neighborhood": {"name": "Malabar"}},
)


@pytest.fixture
def providers(monkeypatch, settings):
    """Both providers with their HTTP calls stubbed. Set `.responses` / `.fail` per test."""
    cache.clear()
    settings.MAPBOX_ACCESS_TOKEN = "test-token"

    class Fake:
        calls: list[tuple[str, str, dict]] = []
        fail: set[str] = set()
        responses = {
            ("photon", "/api/"): {"features": [CIWALK, HOUSE, STREET]},
            ("photon", "/reverse"): {"features": [HOUSE]},
            ("mapbox", "/forward"): {"features": []},
            ("mapbox", "/reverse"): {"features": [MAPBOX_KOSAMBI]},
        }

    def stub(source):
        def get(self, path, params):
            Fake.calls.append((source, path, params))
            if source in Fake.fail:
                raise GeocoderError(f"{source} down")
            return Fake.responses[(source, path)]

        return get

    monkeypatch.setattr(Photon, "_get", stub("photon"))
    monkeypatch.setattr(Mapbox, "_get", stub("mapbox"))
    yield Fake
    cache.clear()


def test_photon_results_become_places_addresses_and_streets(client, providers, settings):
    settings.MAPBOX_ACCESS_TOKEN = ""  # Photon only

    ciwalk, house, street = client.get("/api/geocode", {"q": "braga"}).json()

    assert ciwalk == {
        "id": "photon-W123",
        "name": "Cihampelas Walk (CiWalk)",
        "kind": "landmark",
        "context": "Jalan Cihampelas 160, Cipaganti, Bandung",
        "address": "Jalan Cihampelas 160",
        "lon": 107.6044,
        "lat": -6.8935,
        "source": "photon",
    }
    assert (house["name"], house["kind"], house["context"]) == (
        "Jalan Braga 12",
        "address",
        "Braga, Bandung",
    )
    assert (street["name"], street["kind"]) == ("Jalan Braga", "street")
    # Ranked towards Bandung and limited to Bandung Raya.
    params = providers.calls[0][2]
    assert params["bbox"] == "107.25,-7.25,107.95,-6.7"
    assert (params["lon"], params["lat"]) == (107.6098, -6.9147)
    assert {source for source, _, _ in providers.calls} == {"photon"}


def test_mapbox_places_are_merged_with_osm_streets(client, providers):
    providers.responses[("mapbox", "/forward")] = {"features": [MAPBOX_KOSAMBI, MAPBOX_KOSAMBI_1]}
    providers.responses[("photon", "/api/")] = {"features": [STREET, PHOTON_KOSAMBI]}

    results = client.get("/api/geocode", {"q": "Pasar Kosambi"}).json()

    # The exact match comes first; Photon's copy of the same market is dropped.
    assert [(r["name"], r["source"]) for r in results] == [
        ("Pasar Kosambi", "mapbox"),
        ("Pasar Kosambi 1", "mapbox"),
        ("Jalan Braga", "photon"),
    ]
    kosambi, kosambi_1 = results[0], results[1]
    assert kosambi["id"] == "mapbox-abc"
    assert kosambi["kind"] == "landmark"
    assert kosambi["address"] == "Jl. A. Yani No.221-223"
    assert kosambi["context"] == "Jl. A. Yani No.221-223, Kebon Pisang, Bandung"
    assert kosambi_1["address"] == ""  # "Bandung" there was the city, not a street
    assert kosambi_1["context"] == "Malabar, Bandung"

    _, _, params = next(call for call in providers.calls if call[0] == "mapbox")
    assert params["country"] == "id"
    assert params["proximity"] == "107.6098,-6.9147"
    assert params["auto_complete"] == "true"


def test_mapbox_results_are_never_cached_but_photon_results_are(client, providers):
    client.get("/api/geocode", {"q": "jalan braga"})
    client.get("/api/geocode", {"q": "Jalan  Braga"})

    sources = [source for source, _, _ in providers.calls]
    assert sources.count("mapbox") == 2
    assert sources.count("photon") == 1


def test_one_provider_failing_still_returns_the_others(client, providers):
    providers.fail = {"mapbox"}

    response = client.get("/api/geocode", {"q": "braga"})

    assert response.status_code == 200
    assert {r["source"] for r in response.json()} == {"photon"}


def test_every_provider_failing_is_a_503(client, providers):
    providers.fail = {"mapbox", "photon"}

    assert client.get("/api/geocode", {"q": "braga"}).status_code == 503
    assert client.get("/api/geocode/reverse", {"lon": 107.6, "lat": -6.9}).status_code == 503


def test_reverse_names_a_point_by_its_street_first(client, providers):
    response = client.get("/api/geocode/reverse", {"lon": 107.6091, "lat": -6.9175})

    assert (response.json()["name"], response.json()["source"]) == ("Jalan Braga 12", "photon")
    assert [source for source, _, _ in providers.calls] == ["photon"]


def test_reverse_falls_back_to_mapbox(client, providers):
    providers.fail = {"photon"}

    response = client.get("/api/geocode/reverse", {"lon": 107.6221, "lat": -6.9198})

    assert (response.json()["name"], response.json()["source"]) == ("Pasar Kosambi", "mapbox")


def test_short_queries_are_rejected(client, providers):
    assert client.get("/api/geocode", {"q": "ab"}).status_code == 422
    assert providers.calls == []


def test_many_mapbox_places_do_not_crowd_out_osm_streets(client, providers):
    places = [mapbox_feature(f"p{i}", 107.6 + i / 100, -6.9, name=f"Toko {i}") for i in range(6)]
    providers.responses[("mapbox", "/forward")] = {"features": places}
    providers.responses[("photon", "/api/")] = {"features": [STREET]}

    names = [r["name"] for r in client.get("/api/geocode", {"q": "toko"}).json()]

    assert names[:3] == ["Toko 0", "Jalan Braga", "Toko 1"]
    assert len(names) == 6


def test_a_client_can_ask_one_provider(client, providers):
    providers.responses[("mapbox", "/forward")] = {"features": [MAPBOX_KOSAMBI]}

    mapbox = client.get("/api/geocode", {"q": "kosambi", "source": "mapbox"}).json()
    photon = client.get("/api/geocode", {"q": "kosambi", "source": "photon"}).json()

    assert {r["source"] for r in mapbox} == {"mapbox"}
    assert {r["source"] for r in photon} == {"photon"}
    assert client.get("/api/geocode", {"q": "kosambi", "source": "google"}).status_code == 422


def test_asking_for_mapbox_without_a_token_gives_no_results(client, providers, settings):
    settings.MAPBOX_ACCESS_TOKEN = ""

    response = client.get("/api/geocode", {"q": "kosambi", "source": "mapbox"})

    assert (response.status_code, response.json()) == (200, [])
