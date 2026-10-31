"""Trip planning: A* over the transit network, then rank the options.

One A* search finds the cheapest path for one cost function, so the planner runs a few:

- fastest:  travel time, with walking weighted a little higher than riding
- cheapest: travel time plus the fare converted to seconds
- reliable: long waits and transfers weighted heavily, so frequent direct services win

and then a couple more "fastest" searches that penalise the routes already found, to
surface genuine alternatives. Distinct options are scored on time, cost and availability.
"""

import heapq
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
from shapely.geometry import LineString
from shapely.ops import substring

from transit.etl.transform import TO_METRIC
from transit.routing.astar import astar
from transit.routing.network import ALIGHT, BOARD, RIDE, WALK, Edge, Network

# Penalty (seconds of generalised cost) per already-used route when looking for alternatives.
ALTERNATIVE_PENALTY_S = 900
ALTERNATIVE_ROUNDS = 2
# Options much slower than the fastest one are dropped unless they are best at something.
MAX_SLOWDOWN = 2.5

SORT_WEIGHTS = {
    # (time, cost, availability)
    "balanced": (0.45, 0.30, 0.25),
    "time": (1.0, 0.0, 0.0),
    "cost": (0.0, 1.0, 0.0),
    "availability": (0.0, 0.0, 1.0),
}


@dataclass(frozen=True)
class Weights:
    name: str
    ride: float = 1.0
    walk: float = 1.2
    wait: float = 1.0
    fare_s_per_idr: float = 0.0
    board_s: float = 60.0  # friction of each boarding, which is what makes transfers cost

    def cost(self, edge: Edge, penalty: dict[int, float] | None = None) -> float:
        """Generalised cost of an edge, in seconds."""
        if edge.kind == RIDE:
            return edge.time_s * self.ride + edge.fare_idr * self.fare_s_per_idr
        if edge.kind == BOARD:
            return (
                edge.time_s * self.wait
                + self.board_s
                + edge.fare_idr * self.fare_s_per_idr
                + (penalty.get(edge.route, 0.0) if penalty else 0.0)
            )
        if edge.kind == WALK:
            return edge.time_s * self.walk
        return 0.0


PROFILES = [
    Weights("fastest"),
    Weights("cheapest", fare_s_per_idr=0.25),
    Weights("reliable", walk=1.5, wait=2.5, board_s=300.0),
]


@dataclass
class Place:
    lon: float
    lat: float
    name: str = ""


@dataclass
class Leg:
    mode: str
    from_place: Place
    to_place: Place
    distance_m: float = 0.0
    duration_s: float = 0.0
    wait_s: float = 0.0
    fare_idr: int = 0
    route: int | None = None
    stop_count: int = 0
    depart_at: datetime | None = None
    arrive_at: datetime | None = None
    coords: list[tuple[float, float]] = field(default_factory=list)
    from_measure: float = 0.0
    to_measure: float = 0.0
    available: bool = True


@dataclass
class Option:
    legs: list[Leg]
    depart_at: datetime
    arrive_at: datetime
    found_by: set[str]
    duration_s: float = 0.0
    fare_idr: int = 0
    walk_m: float = 0.0
    wait_s: float = 0.0
    transfers: int = 0
    availability: float = 1.0
    uses_placeholder: bool = False
    scores: dict[str, float] = field(default_factory=dict)
    labels: list[str] = field(default_factory=list)

    @property
    def signature(self) -> tuple:
        return tuple(leg.route for leg in self.legs if leg.route is not None) or ("walk",)


def _xy(place: Place) -> np.ndarray:
    x, y = TO_METRIC.transform(place.lon, place.lat)
    return np.array([x, y])


class _Search:
    """Origin, destination and the per-query edges joining them to the network."""

    def __init__(self, net: Network, origin: Place, destination: Place, depart_at: datetime):
        self.net = net
        self.origin, self.destination = origin, destination
        self.origin_xy, self.dest_xy = _xy(origin), _xy(destination)
        n = net.stop_count
        self.start, self.goal = 2 * n, 2 * n + 1
        walk = net.walk

        def walk_edge(to: int, xy_a: np.ndarray, xy_b: np.ndarray) -> Edge:
            metres = float(np.hypot(*(xy_a - xy_b))) * walk.detour_factor
            return Edge(to, WALK, metres / walk.speed_ms, 0, metres)

        self.access = [
            walk_edge(s, self.origin_xy, net.stop_xy[s]) for s in self._near(self.origin_xy)
        ]
        self.egress = {
            s: walk_edge(self.goal, net.stop_xy[s], self.dest_xy) for s in self._near(self.dest_xy)
        }
        direct = float(np.hypot(*(self.origin_xy - self.dest_xy)))
        self.direct_walk = (
            walk_edge(self.goal, self.origin_xy, self.dest_xy)
            if direct <= walk.max_direct_walk_m
            else None
        )
        at = depart_at.time()
        self.closed = {i for i, route in enumerate(net.routes) if not route.operates_at(at)}
        # Straight-line distance to the destination for every stop, for the heuristic.
        self.to_dest = np.hypot(*(net.stop_xy - self.dest_xy).T).tolist() if n else []

    def _near(self, xy: np.ndarray) -> list[int]:
        walk = self.net.walk
        stops = self.net.nearest_stops_per_route(tuple(xy), walk.max_access_m)
        return stops or self.net.nearest_stops_per_route(tuple(xy), walk.max_access_fallback_m)

    def run(self, weights: Weights, penalty: dict[int, float]) -> list[tuple[int, Edge]] | None:
        net, n, start, goal = self.net, self.net.stop_count, self.start, self.goal

        def cost(edge: Edge) -> float:
            return weights.cost(edge, penalty)

        def neighbours(node: int):
            if node == start:
                for edge in self.access:
                    yield edge.to, cost(edge), edge
                if self.direct_walk:
                    yield goal, cost(self.direct_walk), self.direct_walk
                return
            for edge in net.adjacency[node]:
                if edge.kind == BOARD and edge.route in self.closed:
                    continue
                yield edge.to, cost(edge), edge
            if node < n and node in self.egress:
                edge = self.egress[node]
                yield goal, cost(edge), edge

        # Nothing moves faster than max_speed_ms, and every second costs at least this much.
        per_metre = min(weights.ride, weights.walk) / net.max_speed_ms
        origin_h = float(np.hypot(*(self.origin_xy - self.dest_xy))) * per_metre

        def heuristic(node: int) -> float:
            if node == goal:
                return 0.0
            if node == start:
                return origin_h
            return self.to_dest[node % n] * per_metre

        result = astar(start, goal, neighbours, heuristic)
        if result is None:
            return None
        return [(node, edge) for node, edge in result.steps[1:]]

    def place(self, node: int) -> Place:
        if node == self.start:
            return self.origin
        if node == self.goal:
            return self.destination
        stop = node % self.net.stop_count
        lon, lat = self.net.stop_lonlat[stop]
        return Place(lon, lat, self.net.stop_name[stop])

    def to_option(self, steps: list[tuple[int, Edge]], depart_at: datetime, found_by: str):
        net, n = self.net, self.net.stop_count
        legs: list[Leg] = []
        clock = depart_at
        prev = self.start
        for node, edge in steps:
            if edge.kind == WALK:
                if legs and legs[-1].mode == "walk":
                    leg = legs[-1]
                else:
                    leg = Leg("walk", self.place(prev), self.place(node), depart_at=clock)
                    leg.coords = [(leg.from_place.lon, leg.from_place.lat)]
                    legs.append(leg)
                leg.to_place = self.place(node)
                leg.coords.append((leg.to_place.lon, leg.to_place.lat))
                leg.distance_m += edge.distance_m
                leg.duration_s += edge.time_s
                clock += timedelta(seconds=edge.time_s)
                leg.arrive_at = clock
            elif edge.kind == BOARD:
                route = net.routes[edge.route]
                stop = node - n
                leg = Leg(
                    route.mode,
                    self.place(stop),
                    self.place(stop),
                    route=edge.route,
                    wait_s=edge.time_s,
                    depart_at=clock + timedelta(seconds=edge.time_s),
                    from_measure=net.stop_measure[stop],
                    to_measure=net.stop_measure[stop],
                    available=route.operates_at((clock + timedelta(seconds=edge.time_s)).time()),
                )
                clock = leg.depart_at
                legs.append(leg)
            elif edge.kind == RIDE:
                leg = legs[-1]
                leg.distance_m += edge.distance_m
                leg.duration_s += edge.time_s
                leg.stop_count += 1
                clock += timedelta(seconds=edge.time_s)
            elif edge.kind == ALIGHT:
                leg = legs[-1]
                route = net.routes[leg.route]
                leg.to_place = self.place(node)
                leg.to_measure = net.stop_measure[node]
                leg.arrive_at = clock
                leg.fare_idr = route.fare_for(leg.distance_m)
                leg.coords = _cut(route.line, route.length_m, leg.from_measure, leg.to_measure)
            prev = node

        # Stepping from a stop onto the same spot on another route is not worth showing.
        legs = [leg for leg in legs if leg.route is not None or leg.distance_m >= 1]
        rides = [leg for leg in legs if leg.route is not None]
        option = Option(legs=legs, depart_at=depart_at, arrive_at=clock, found_by={found_by})
        option.duration_s = (clock - depart_at).total_seconds()
        option.fare_idr = sum(leg.fare_idr for leg in rides)
        option.walk_m = sum(leg.distance_m for leg in legs if leg.route is None)
        option.wait_s = sum(leg.wait_s for leg in rides)
        option.transfers = max(0, len(rides) - 1)
        option.availability = 1.0
        for leg in rides:
            route = net.routes[leg.route]
            option.availability *= _frequency_score(route.headway_min) if leg.available else 0.0
        option.uses_placeholder = any(net.routes[leg.route].is_placeholder for leg in rides)
        return option


def _frequency_score(headway_min: float) -> float:
    """1.0 for a vehicle every minute, 0.5 every 30 minutes, falling off after that."""
    return 1.0 / (1.0 + headway_min / 30.0)


def _cut(line: LineString, length_m: float, start_m: float, end_m: float):
    if length_m <= 0:
        return list(line.coords)
    part = substring(line, start_m / length_m, end_m / length_m, normalized=True)
    coords = list(part.coords) if part.geom_type == "LineString" else [part.coords[0]] * 2
    return [(round(x, 6), round(y, 6)) for x, y in coords]


def plan(
    net: Network,
    origin: Place,
    destination: Place,
    depart_at: datetime,
    sort: str = "balanced",
    max_options: int = 5,
) -> list[Option]:
    search = _Search(net, origin, destination, depart_at)
    options: dict[tuple, Option] = {}

    def add(steps, found_by: str) -> Option | None:
        if steps is None:
            return None
        option = search.to_option(steps, depart_at, found_by)
        if option.signature in options:
            options[option.signature].found_by.add(found_by)
        else:
            options[option.signature] = option
        return option

    for weights in PROFILES:
        add(search.run(weights, {}), weights.name)

    penalty: dict[int, float] = {}
    for round_ in range(ALTERNATIVE_ROUNDS):
        for option in list(options.values()):
            for route in option.signature:
                if route != "walk":
                    penalty[route] = ALTERNATIVE_PENALTY_S * (round_ + 1)
        add(search.run(PROFILES[0], penalty), "alternative")

    if search.direct_walk:
        add([(search.goal, search.direct_walk)], "walk")

    return rank(list(options.values()), sort, max_options)


def rank(options: list[Option], sort: str = "balanced", max_options: int = 5) -> list[Option]:
    if not options:
        return []
    fastest = min(option.duration_s for option in options)
    cheapest = min(option.fare_idr for option in options)
    most_available = max(option.availability for option in options)

    for option in options:
        option.scores = {
            "time": fastest / option.duration_s if option.duration_s else 1.0,
            # The constant keeps a Rp 0 vs Rp 500 difference from dominating.
            "cost": (cheapest + 2000) / (option.fare_idr + 2000),
            "availability": option.availability / most_available if most_available else 0.0,
        }
        w_time, w_cost, w_avail = SORT_WEIGHTS.get(sort, SORT_WEIGHTS["balanced"])
        option.scores["overall"] = (
            w_time * option.scores["time"]
            + w_cost * option.scores["cost"]
            + w_avail * option.scores["availability"]
        )
        option.labels = []
        if option.duration_s == fastest:
            option.labels.append("fastest")
        if option.fare_idr == cheapest:
            option.labels.append("cheapest")
        if most_available and option.availability == most_available:
            option.labels.append("most_available")

    kept = [
        option for option in options if option.labels or option.duration_s <= MAX_SLOWDOWN * fastest
    ]
    kept.sort(key=lambda option: (-option.scores["overall"], option.duration_s))
    return kept[:max_options]


@dataclass
class TravelTime:
    minutes: float
    transfers: int
    walk_only: bool = False


def travel_times(
    net: Network,
    destination: Place,
    origins: list[Place],
    depart_at: datetime,
    max_minutes: float = 150,
) -> list[TravelTime | None]:
    """Fastest travel time from each origin to one destination, from a single search.

    One A* per origin would repeat almost the same work for every neighbourhood. Instead
    this runs Dijkstra once, backwards from the destination over reversed edges, which
    gives the cost of getting from every stop to the destination. Each origin then only
    has to add its walk to the nearby stops. Uses the "fastest" weights; the times
    returned are real minutes, without the boarding friction.
    """
    weights = PROFILES[0]
    search = _Search(net, destination, destination, depart_at)
    reverse = net.reverse_adjacency
    limit = max_minutes * 60 * 2  # generalised cost runs above real time

    # cost, real seconds and boardings from each node to the destination.
    best: dict[int, tuple[float, float, int]] = {}
    heap = []
    for stop, edge in search.egress.items():
        heapq.heappush(heap, (weights.cost(edge), edge.time_s, 0, stop))
    while heap:
        cost, seconds, boardings, node = heapq.heappop(heap)
        if node in best or cost > limit:
            continue
        best[node] = (cost, seconds, boardings)
        for prev, edge in reverse[node]:
            if prev in best or (edge.kind == BOARD and edge.route in search.closed):
                continue
            heapq.heappush(
                heap,
                (
                    cost + weights.cost(edge),
                    seconds + edge.time_s,
                    boardings + (edge.kind == BOARD),
                    prev,
                ),
            )

    walk = net.walk
    results: list[TravelTime | None] = []
    for origin in origins:
        xy = _xy(origin)
        candidates: list[tuple[float, TravelTime]] = []
        direct = float(np.hypot(*(xy - search.dest_xy))) * walk.detour_factor
        if direct <= walk.max_direct_walk_m * walk.detour_factor:
            seconds = direct / walk.speed_ms
            candidates.append((seconds * weights.walk, TravelTime(seconds / 60, 0, True)))
        for stop in search._near(xy):
            if stop not in best:
                continue
            cost, seconds, boardings = best[stop]
            walked = float(np.hypot(*(xy - net.stop_xy[stop]))) * walk.detour_factor
            access = walked / walk.speed_ms
            candidates.append(
                (
                    cost + access * weights.walk,
                    TravelTime((seconds + access) / 60, max(0, boardings - 1)),
                )
            )
        fastest = min(candidates, key=lambda c: c[0], default=None)
        results.append(fastest[1] if fastest and fastest[1].minutes <= max_minutes else None)
    return results
