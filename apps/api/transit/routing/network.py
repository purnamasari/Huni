"""The in-memory routing graph, built from the transit tables.

Nodes are numbered so they fit in plain lists:

- `s` in [0, N): standing at stop s (on the street, not on a vehicle)
- `N + s`: on the vehicle of stop s's route, at stop s

Edges:

- BOARD   stop s → vehicle s     wait for the vehicle (half the headway) and pay the fare
- RIDE    vehicle s → vehicle s+1 along the same route
- ALIGHT  vehicle s → stop s
- WALK    stop s → stop t on another route, within the transfer distance

The origin and destination are added per query by the planner. Distances are metres in UTM
48S (EPSG:32748).
"""

import threading
from dataclasses import dataclass, field
from datetime import time

import numpy as np
import shapely
from shapely.geometry import LineString

from transit.etl.transform import TO_METRIC
from transit.models import ImportRun, Route, RouteStop
from transit.profiles import WalkProfile, walk_profile

BOARD, RIDE, ALIGHT, WALK = range(4)


@dataclass(frozen=True)
class Edge:
    to: int
    kind: int
    time_s: float
    fare_idr: float
    distance_m: float
    route: int = -1


@dataclass
class RouteInfo:
    id: int
    name: str
    code: str
    mode: str
    color: str
    origin_name: str
    destination_name: str
    boarding: str
    fare_base_idr: int
    fare_per_km_idr: int
    fare_max_idr: int | None
    speed_ms: float
    headway_min: float
    service_start: time
    service_end: time
    is_placeholder: bool
    line: LineString  # lon/lat, for cutting leg geometry
    length_m: float

    def fare_for(self, distance_m: float) -> int:
        fare = self.fare_base_idr + self.fare_per_km_idr * distance_m / 1000
        if self.fare_max_idr is not None:
            fare = min(fare, self.fare_max_idr)
        # Round up to the nearest Rp 500, like cash fares.
        return int(-(-fare // 500) * 500)

    def operates_at(self, at: time) -> bool:
        if self.service_start <= self.service_end:
            return self.service_start <= at <= self.service_end
        return at >= self.service_start or at <= self.service_end


@dataclass
class Network:
    version: int
    walk: WalkProfile
    routes: list[RouteInfo]
    stop_route: list[int]
    stop_name: list[str]
    stop_measure: list[float]
    stop_virtual: list[bool]
    stop_lonlat: list[tuple[float, float]]
    stop_xy: np.ndarray
    adjacency: list[list[Edge]] = field(default_factory=list)
    max_speed_ms: float = 1.0
    tree: shapely.STRtree | None = None
    _reverse: list[list[tuple[int, Edge]]] | None = None

    @property
    def stop_count(self) -> int:
        return len(self.stop_route)

    @property
    def reverse_adjacency(self) -> list[list[tuple[int, Edge]]]:
        """For every node, the (from node, edge) pairs that lead into it. Built on first use."""
        if self._reverse is None:
            reverse: list[list[tuple[int, Edge]]] = [[] for _ in self.adjacency]
            for node, edges in enumerate(self.adjacency):
                for edge in edges:
                    reverse[edge.to].append((node, edge))
            self._reverse = reverse
        return self._reverse

    def nearest_stops_per_route(self, xy: tuple[float, float], radius_m: float) -> list[int]:
        """The closest stop of each route within radius_m of xy."""
        candidates = self.tree.query(shapely.Point(xy), predicate="dwithin", distance=radius_m)
        best: dict[int, tuple[float, int]] = {}
        for stop in candidates.tolist():
            dist = float(np.hypot(*(self.stop_xy[stop] - xy)))
            route = self.stop_route[stop]
            if route not in best or dist < best[route][0]:
                best[route] = (dist, stop)
        return [stop for _, stop in best.values()]


def build_network(
    routes: list[RouteInfo],
    stops: list[tuple[int, str, float, bool, tuple[float, float]]],
    walk: WalkProfile,
    version: int = 0,
) -> Network:
    """Build the graph. `stops` are (route index, name, measure, is_virtual, lon/lat),
    grouped by route and in travel order within each route."""
    lonlat = [stop[4] for stop in stops]
    xs, ys = TO_METRIC.transform([p[0] for p in lonlat], [p[1] for p in lonlat])
    xy = np.column_stack([xs, ys]) if stops else np.zeros((0, 2))
    net = Network(
        version=version,
        walk=walk,
        routes=routes,
        stop_route=[stop[0] for stop in stops],
        stop_name=[stop[1] for stop in stops],
        stop_measure=[stop[2] for stop in stops],
        stop_virtual=[stop[3] for stop in stops],
        stop_lonlat=lonlat,
        stop_xy=xy,
        max_speed_ms=max([walk.speed_ms] + [route.speed_ms for route in routes]),
    )
    n = net.stop_count
    adjacency: list[list[Edge]] = [[] for _ in range(2 * n)]

    for s in range(n):
        route_index = net.stop_route[s]
        route = routes[route_index]
        adjacency[s].append(
            Edge(n + s, BOARD, route.headway_min * 60 / 2, route.fare_base_idr, 0, route_index)
        )
        adjacency[n + s].append(Edge(s, ALIGHT, 0, 0, 0, route_index))
        if s + 1 < n and net.stop_route[s + 1] == route_index:
            distance = net.stop_measure[s + 1] - net.stop_measure[s]
            adjacency[n + s].append(
                Edge(
                    n + s + 1,
                    RIDE,
                    distance / route.speed_ms,
                    route.fare_per_km_idr * distance / 1000,
                    distance,
                    route_index,
                )
            )

    for s, t, distance in _transfers(net, walk.max_transfer_m):
        walked = distance * walk.detour_factor
        adjacency[s].append(Edge(t, WALK, walked / walk.speed_ms, 0, walked))

    net.adjacency = adjacency
    net.tree = shapely.STRtree(shapely.points(xy)) if n else None
    return net


def _transfers(net: Network, radius_m: float):
    """(stop, stop on another route, distance), keeping the nearest stop of each other route."""
    if net.stop_count == 0:
        return []
    points = shapely.points(net.stop_xy)
    tree = shapely.STRtree(points)
    src, dst = tree.query(points, predicate="dwithin", distance=radius_m)
    route = np.asarray(net.stop_route)
    keep = route[src] != route[dst]
    src, dst = src[keep], dst[keep]
    dist = np.hypot(*(net.stop_xy[src] - net.stop_xy[dst]).T)
    order = np.lexsort((dist, route[dst], src))
    src, dst, dist = src[order], dst[order], dist[order]
    first = np.ones(len(src), dtype=bool)
    first[1:] = (src[1:] != src[:-1]) | (route[dst][1:] != route[dst][:-1])
    return zip(src[first].tolist(), dst[first].tolist(), dist[first].tolist(), strict=True)


def load_network() -> Network:
    run = ImportRun.objects.order_by("-id").first()
    routes, index = [], {}
    for route in Route.objects.order_by("id"):
        index[route.id] = len(routes)
        routes.append(
            RouteInfo(
                id=route.id,
                name=route.name,
                code=route.code,
                mode=route.mode,
                color=route.color,
                origin_name=route.origin_name,
                destination_name=route.destination_name,
                boarding=route.boarding,
                fare_base_idr=route.fare_base_idr,
                fare_per_km_idr=route.fare_per_km_idr,
                fare_max_idr=route.fare_max_idr,
                speed_ms=route.avg_speed_kmh / 3.6,
                headway_min=route.headway_min,
                service_start=route.service_start,
                service_end=route.service_end,
                is_placeholder=route.service_is_placeholder,
                line=LineString(route.geom.coords),
                length_m=route.length_m,
            )
        )
    stops = [
        (index[route_id], name, measure, virtual, (geom.x, geom.y))
        for route_id, name, measure, virtual, geom in RouteStop.objects.order_by(
            "route_id", "sequence"
        ).values_list("route_id", "name", "measure_m", "is_virtual", "geom")
    ]
    return build_network(routes, stops, walk_profile(), version=run.id if run else 0)


_cache: dict[str, Network] = {}
_lock = threading.Lock()


def get_network() -> Network:
    """The network for the latest import, rebuilt when a new import has run."""
    run = ImportRun.objects.order_by("-id").values_list("id", flat=True).first() or 0
    with _lock:
        cached = _cache.get("network")
        if cached is None or cached.version != run:
            _cache["network"] = load_network()
        return _cache["network"]
