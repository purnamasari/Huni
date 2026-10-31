import math
import random

import pytest
from shapely.geometry import LineString

from transit.etl.transform import (
    Anchor,
    name_score,
    order_pieces,
    parse_route_name,
    place_stops,
)
from transit.models import Mode
from transit.profiles import classify_mode, service_for


@pytest.mark.parametrize(
    ("name", "code", "places"),
    [
        ("09: Dago → Stasiun Hall", "09", ["Dago", "Stasiun Hall"]),
        ("Koridor 1: Cibeureum → Cibiru", "Koridor 1", ["Cibeureum", "Cibiru"]),
        ("07: Derwati → Pusdai (Derwati → Cicaheum)", "07", ["Derwati", "Pusdai"]),
        ("Cimahi → Permata via Puri Cipageran", "", ["Cimahi", "Permata"]),
        ("Summarecon: Shuttle Cluster Kawasan", "Summarecon", ["Shuttle Cluster Kawasan"]),
    ],
)
def test_parse_route_name(name, code, places):
    parsed = parse_route_name(name)
    assert parsed.code == code
    assert parsed.places == places


def test_name_score_handles_terminal_words_and_spelling():
    assert name_score("Dago", "Terminal Dago") == 1.0
    assert name_score("Buahbatu", "Terminal Angkot Buah Batu-GBA") >= 0.9
    assert name_score("Dago", "Terminal Leuwipanjang") == 0.0


def test_classify_mode():
    assert classify_mode("Commuter Line Bandung Raya: Padalarang → Cicalengka") == Mode.RAIL
    assert classify_mode("Koridor 4: Dago → Leuwipanjang") == Mode.BUS
    assert classify_mode("Elf: Tegallega → Pangalengan") == Mode.MINIBUS
    assert classify_mode("09: Dago → Stasiun Hall") == Mode.ANGKOT


def _shuffled(pieces, seed=1):
    """Pieces in random order, some reversed, like the delivered files."""
    rng = random.Random(seed)
    pieces = [list(p) if rng.random() < 0.5 else list(reversed(p)) for p in pieces]
    rng.shuffle(pieces)
    return pieces


def test_order_pieces_rebuilds_travel_order_from_shuffled_pieces():
    xs = range(0, 3001, 250)
    straight = [[(x0, 0.0), (x1, 0.0)] for x0, x1 in zip(xs, xs[1:], strict=False)]

    ordered = order_pieces(
        _shuffled(straight),
        [""] * len(straight),
        origin=Anchor("Terminal East", (3010.0, 5.0)),
        destination=Anchor("Terminal West", (-10.0, 0.0)),
    )

    assert ordered.coords[0] == (3000.0, 0.0)
    assert ordered.coords[-1] == (0.0, 0.0)
    assert [x for x, _ in ordered.coords] == sorted((x for x, _ in ordered.coords), reverse=True)
    assert ordered.coverage == pytest.approx(1.0)
    assert ordered.orientation == "names"


def test_order_pieces_keeps_a_loop_the_vehicle_drives():
    # A → J → K → B along the street, plus a loop J → north → K. A shortest path would skip
    # the loop; the route data says the vehicle drives it.
    pieces = [
        [(0.0, 0.0), (1000.0, 0.0)],
        [(1000.0, 0.0), (1400.0, 0.0)],
        [(1400.0, 0.0), (2000.0, 0.0)],
        [(1000.0, 0.0), (1000.0, 400.0), (1400.0, 400.0), (1400.0, 0.0)],
    ]

    ordered = order_pieces(pieces, [""] * 4, Anchor("A", (0.0, 0.0)), Anchor("B", (2000.0, 0.0)))

    assert LineString(ordered.coords).length == pytest.approx(2800)
    assert (1000.0, 400.0) in ordered.coords


def test_order_pieces_respects_oneway():
    north = [(0.0, 0.0), (0.0, 100.0), (1000.0, 100.0), (1000.0, 0.0)]
    south = [(0.0, 0.0), (1000.0, 0.0)]

    # North may only be driven west → east; south (oneway=-1) only east → west.
    ordered = order_pieces(
        [south, north], ["-1", "yes"], Anchor("A", (0.0, 0.0)), Anchor("B", (1000.0, 0.0))
    )

    assert ordered.coords == north
    assert not ordered.oneway_relaxed


def test_order_pieces_bridges_gaps():
    pieces = [[(0.0, 0.0), (1000.0, 0.0)], [(1050.0, 0.0), (2000.0, 0.0)]]

    ordered = order_pieces(pieces, ["", ""], Anchor("A", (0.0, 0.0)), Anchor("B", (2000.0, 0.0)))

    assert ordered.bridged_gap_m == pytest.approx(50)
    assert ordered.coords[0] == (0.0, 0.0)
    assert ordered.coords[-1] == (2000.0, 0.0)


def test_order_pieces_loop_returns_to_start():
    square = [(0.0, 0.0), (500.0, 0.0), (500.0, 500.0), (0.0, 500.0), (0.0, 0.0)]
    pieces = [square[i : i + 2] for i in range(4)]

    ordered = order_pieces(pieces, ["yes"] * 4, Anchor("Start", (0.0, 0.0)), None, loop=True)

    assert ordered.is_loop
    assert ordered.coords[0] == ordered.coords[-1] == (0.0, 0.0)
    assert ordered.coords[1] == (500.0, 0.0)  # the way the oneway tags allow
    assert ordered.coverage == pytest.approx(1.0)


def test_place_stops_spaces_virtual_stops_for_hail_routes():
    line = LineString([(0, 0), (1000, 0)])
    service = service_for("09: A → B", Mode.ANGKOT)  # hail, 250 m placeholder spacing

    stops = place_stops(line, [], service, "A", "B", [("Jalan Contoh", line)])

    assert [round(stop.measure_m) for stop in stops] == [0, 250, 500, 750, 1000]
    assert stops[0].name == "A" and not stops[0].is_virtual
    assert stops[1].name == "Jalan Contoh" and stops[1].is_virtual


def test_place_stops_uses_the_stop_list_of_fixed_stop_routes():
    line = LineString([(0, 0), (2000, 0)])
    service = service_for("Koridor 9: A → B", Mode.BUS)
    points = [(f"Halte {i}", (x, 20.0)) for i, x in enumerate([1500, 300, 900, 1900])]
    points.append(("Far away", (1000.0, 900.0)))

    stops = place_stops(line, points, service, "A", "B", [])

    assert [stop.name for stop in stops] == ["A", "Halte 1", "Halte 2", "Halte 0", "Halte 3"]
    assert not any(stop.is_virtual for stop in stops)
    assert all(math.isclose(stop.xy[1], 0) for stop in stops)
