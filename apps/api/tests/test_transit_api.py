"""The import pipeline and API end to end, on two small crossing routes."""

import pytest

from tests.transit_fixtures import EAST, NORTH, SOUTH, WEST, write_network
from transit.etl.pipeline import run_import
from transit.models import Route


@pytest.fixture
def network(tmp_path, db):
    return run_import(None, write_network(tmp_path / "kml"), log=lambda _: None)


def test_import_orders_routes_and_creates_stops(network):
    assert network.route_count == 2
    assert network.report["orientation"] == {"names": 2}

    t1 = Route.objects.get(name="T1: West → East")
    assert t1.code == "T1"
    assert t1.color == "#F15A29"
    assert t1.coverage == pytest.approx(1.0)
    assert t1.geom.coords[0] == pytest.approx(WEST)
    assert t1.geom.coords[-1] == pytest.approx(EAST)
    assert t1.length_m == pytest.approx(4415, rel=0.01)  # 0.04° of longitude at 6.9° S

    t2 = Route.objects.get(name="T2: North → South")
    # Its KML lists the destination first; the name decides the direction.
    assert t2.geom.coords[0] == pytest.approx(NORTH)

    stops = list(t1.stops.all())
    assert stops[0].name == "Terminal West"
    assert stops[-1].name == "Terminal East"
    assert all(a.measure_m < b.measure_m for a, b in zip(stops, stops[1:], strict=False))
    assert any(stop.is_virtual for stop in stops)  # angkot: hail anywhere


def test_plan_finds_the_transfer_between_routes(client, network):
    response = client.post(
        "/api/transit/plan",
        {
            "origin": {"lon": WEST[0] + 0.001, "lat": WEST[1], "name": "Home"},
            "destinations": [{"lon": SOUTH[0], "lat": SOUTH[1] + 0.001, "name": "School"}],
            "depart_at": "2026-11-02T08:00:00",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["depart_at"].startswith("2026-11-02T08:00:00+07:00")
    (segment,) = body["segments"]
    best = segment["options"][0]
    rides = [leg["route"]["name"] for leg in best["legs"] if leg["route"]]
    assert rides == ["T1: West → East", "T2: North → South"]
    assert best["transfers"] == 1
    assert best["fare_idr"] > 0
    assert "fastest" in best["labels"]
    assert best["uses_placeholder"]
    assert any("placeholder" in note for note in body["notes"])
    assert all(len(leg["geometry"]["coordinates"]) >= 2 for leg in best["legs"])


def test_plan_chains_multiple_destinations(client, network):
    response = client.post(
        "/api/transit/plan",
        {
            "origin": {"lon": WEST[0], "lat": WEST[1]},
            "destinations": [
                {"lon": EAST[0], "lat": EAST[1]},
                {"lon": EAST[0] + 0.001, "lat": EAST[1]},
            ],
            "depart_at": "2026-11-02T08:00:00",
        },
        content_type="application/json",
    )

    first, second = response.json()["segments"]
    assert first["options"][0]["summary"] == "Angkot T1"
    # The second hop leaves when the first one arrives, and is short enough to walk.
    assert second["options"][0]["depart_at"] == first["options"][0]["arrive_at"]
    assert second["options"][0]["summary"] == "Walk"


def test_plan_skips_routes_that_are_not_running(client, network):
    response = client.post(
        "/api/transit/plan",
        {
            "origin": {"lon": WEST[0], "lat": WEST[1]},
            "destinations": [{"lon": EAST[0], "lat": EAST[1]}],
            "depart_at": "2026-11-02T23:30:00",  # placeholder angkot hours end at 21:00
        },
        content_type="application/json",
    )

    (segment,) = response.json()["segments"]
    assert segment["options"] == []
    assert response.json()["notes"] == ["No route found from Origin to Destination 1."]


def test_routes_places_and_import_report(client, network):
    routes = client.get("/api/transit/routes").json()
    assert {f["properties"]["name"] for f in routes["features"]} == {
        "T1: West → East",
        "T2: North → South",
    }
    assert routes["features"][0]["geometry"]["type"] == "LineString"

    detail = client.get(f"/api/transit/routes/{routes['features'][0]['id']}").json()
    assert detail["service_is_placeholder"] is True
    assert detail["stops"][0]["sequence"] == 0

    places = client.get("/api/transit/places", {"q": "terminal"}).json()
    assert {p["name"] for p in places} == {
        "Terminal West",
        "Terminal East",
        "Terminal North",
        "Terminal South",
    }

    report = client.get("/api/transit/imports/latest").json()
    assert report["route_count"] == 2


def test_commute_times_from_many_origins_in_one_search(client, network):
    response = client.post(
        "/api/transit/commute",
        {
            "destination": {"lon": SOUTH[0], "lat": SOUTH[1], "name": "Office"},
            "origins": [
                {"id": "west", "lon": WEST[0], "lat": WEST[1]},
                {"id": "north", "lon": NORTH[0], "lat": NORTH[1]},
                {"id": "next-door", "lon": SOUTH[0] + 0.002, "lat": SOUTH[1]},
                {"id": "far-away", "lon": 108.5, "lat": -7.5},
            ],
            "depart_at": "2026-11-02T07:30:00",
        },
        content_type="application/json",
    )

    times = {t["id"]: t for t in response.json()["times"]}
    # West rides T1 then changes to T2; north rides T2 straight down.
    assert times["west"]["transfers"] == 1
    assert times["north"]["transfers"] == 0
    assert 0 < times["north"]["minutes"] < times["west"]["minutes"]
    assert times["next-door"]["walk_only"]
    assert times["far-away"]["minutes"] is None


def test_commute_times_match_the_planner(client, network):
    """The one-search shortcut must agree with a full A* plan for the same trip."""
    origin = {"lon": WEST[0] + 0.001, "lat": WEST[1]}
    destination = {"lon": SOUTH[0], "lat": SOUTH[1] + 0.001}
    depart_at = "2026-11-02T08:00:00"

    commute = client.post(
        "/api/transit/commute",
        {"destination": destination, "origins": [{"id": "o", **origin}], "depart_at": depart_at},
        content_type="application/json",
    ).json()
    planned = client.post(
        "/api/transit/plan",
        {"origin": origin, "destinations": [destination], "depart_at": depart_at, "sort": "time"},
        content_type="application/json",
    ).json()

    fastest = min(o["duration_min"] for o in planned["segments"][0]["options"])
    assert commute["times"][0]["minutes"] == pytest.approx(fastest, abs=0.2)


def test_places_needs_two_characters(client, network):
    assert client.get("/api/transit/places", {"q": "t"}).status_code == 422
