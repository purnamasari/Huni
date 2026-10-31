"""Transform: turn each route's unordered way pieces into one directed line with stops.

Neither delivery has the route in travel order: the shapefile rows and the KML placemarks
are individual OSM ways in no particular order or direction. For each route this module

1. projects everything to UTM 48S (EPSG:32748) so distances are in metres,
2. builds a small graph from the pieces (ways share exact vertices where they join), with
   OSM oneway tags as directed edges and straight "bridges" across any gaps in the data,
3. works out which end is the origin by matching the "A → B" names in the route name
   against the terminal/stop names in the KML, falling back to the graph's dead ends,
4. searches for the longest trail from origin to destination through that graph (each
   piece used at most once, oneway respected), which is the route in travel order, and
5. places boarding points along it: the KML stops for fixed-stop services, plus evenly
   spaced virtual stops for hail-anywhere services (angkot, Elf).

The QA numbers (coverage, bridged gaps, relaxed oneway) end up on each Route so suspicious
routes are easy to find.
"""

import heapq
import math
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import LineString, Point

from transit.etl.extract import RawPiece, RawPoint, RawRoute
from transit.models import Boarding, Mode
from transit.profiles import ServiceProfile, classify_mode, service_for

METRIC_SRID = 32748  # WGS 84 / UTM zone 48S, covers Bandung Raya.
TO_METRIC = Transformer.from_crs(4326, METRIC_SRID, always_xy=True)
TO_LONLAT = Transformer.from_crs(METRIC_SRID, 4326, always_xy=True)

XY = tuple[float, float]

# A terminal name and a matched point further apart than this are not the same place.
MAX_ANCHOR_DISTANCE_M = 3000
# A dead end this close to a terminal point is taken as the end of the route.
LEAF_SNAP_M = 500
# Origin and destination closer than this make the route a loop.
LOOP_M = 300
# Stops further than this from the route line are dropped.
MAX_STOP_OFFSET_M = 150
# A fixed-stop service needs at least this many KML points to trust them as its stop list.
MIN_POINTS_FOR_STOP_LIST = 4

_ONEWAY_FORWARD = {"yes", "true", "1"}
_ONEWAY_BACKWARD = {"-1", "reverse"}
_PLACE_STOPWORDS = {"terminal", "subterminal", "stasiun", "pangkalan", "angkot", "elf", "halte"}


@dataclass
class ParsedName:
    code: str
    places: list[str]

    @property
    def origin(self) -> str:
        return self.places[0]

    @property
    def destination(self) -> str:
        return self.places[-1]


def parse_route_name(name: str) -> ParsedName:
    """Split "09: Dago → Stasiun Hall" into code "09" and places ["Dago", "Stasiun Hall"]."""
    code, sep, rest = name.partition(": ")
    if not sep:
        code, rest = "", name
    rest = re.sub(r"\([^)]*\)", "", rest)
    places = [part.strip() for part in rest.split("→") if part.strip()]
    places = [re.sub(r"\s+via\s+.*$", "", place).strip() or place for place in places]
    return ParsedName(code=code.strip(), places=places or [name])


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def name_score(place: str, label: str) -> float:
    """How well a place name from a route name matches a point label, 0..1."""
    place_tokens = [t for t in _tokens(place) if t not in _PLACE_STOPWORDS] or _tokens(place)
    label_tokens = set(_tokens(label))
    if place_tokens and all(token in label_tokens for token in place_tokens):
        return 1.0
    # Spelling varies in whether places are one word: "Buahbatu" / "Buah Batu".
    if "".join(place_tokens) in "".join(_tokens(label)):
        return 0.9
    ratio = SequenceMatcher(None, " ".join(_tokens(place)), " ".join(_tokens(label))).ratio()
    return ratio if ratio >= 0.8 else 0.0


def to_metric(coords: list[tuple[float, float]]) -> list[XY]:
    xs, ys = TO_METRIC.transform([c[0] for c in coords], [c[1] for c in coords])
    return list(zip(xs, ys, strict=True))


def to_lonlat(coords: list[XY]) -> list[tuple[float, float]]:
    lons, lats = TO_LONLAT.transform([c[0] for c in coords], [c[1] for c in coords])
    return [(round(lon, 7), round(lat, 7)) for lon, lat in zip(lons, lats, strict=True)]


class PieceGraph:
    """Vertices of a route's pieces, joined where pieces share a vertex."""

    def __init__(self) -> None:
        self.xy: list[XY] = []
        self._index: dict[tuple[float, float], int] = {}
        # out[a][b] = (length_m, edge id); directed, so oneway pieces only appear one way.
        self.out: list[dict[int, tuple[float, int]]] = []
        self.neighbours: list[set[int]] = []
        self._edge_ids: dict[tuple[int, int], int] = {}
        self.edge_length: list[float] = []
        self.edge_is_bridge: list[bool] = []
        self.bridged_m = 0.0

    def node(self, xy: XY) -> int:
        key = (round(xy[0], 1), round(xy[1], 1))
        if key not in self._index:
            self._index[key] = len(self.xy)
            self.xy.append(xy)
            self.out.append({})
            self.neighbours.append(set())
        return self._index[key]

    def _edge(self, a: int, b: int, length: float, bridge: bool) -> int:
        key = (min(a, b), max(a, b))
        if key not in self._edge_ids:
            self._edge_ids[key] = len(self.edge_length)
            self.edge_length.append(length)
            self.edge_is_bridge.append(bridge)
        return self._edge_ids[key]

    def add_line(self, coords: list[XY], oneway: str = "", bridge: bool = False) -> None:
        oneway = oneway.lower()
        nodes = [self.node(xy) for xy in coords]
        for a, b in zip(nodes, nodes[1:], strict=False):
            if a == b:
                continue
            length = math.dist(self.xy[a], self.xy[b])
            edge = self._edge(a, b, length, bridge)
            if oneway not in _ONEWAY_BACKWARD:
                self.out[a][b] = (length, edge)
            if oneway not in _ONEWAY_FORWARD:
                self.out[b][a] = (length, edge)
            self.neighbours[a].add(b)
            self.neighbours[b].add(a)

    @property
    def leaves(self) -> list[int]:
        return [n for n, nbrs in enumerate(self.neighbours) if len(nbrs) == 1]

    def components(self) -> list[list[int]]:
        seen: set[int] = set()
        result = []
        for start in range(len(self.xy)):
            if start in seen:
                continue
            stack, component = [start], []
            seen.add(start)
            while stack:
                node = stack.pop()
                component.append(node)
                for nbr in self.neighbours[node]:
                    if nbr not in seen:
                        seen.add(nbr)
                        stack.append(nbr)
            result.append(component)
        return result

    def bridge_gaps(self) -> None:
        """Join disconnected parts with straight two-way edges at their closest vertices."""
        components = sorted(self.components(), key=len, reverse=True)
        main, rest = components[0], components[1:]
        while rest:
            tree = shapely.STRtree(shapely.points(np.array([self.xy[n] for n in main])))
            best = None
            for i, component in enumerate(rest):
                points = shapely.points(np.array([self.xy[n] for n in component]))
                (src, dst), dist = tree.query_nearest(
                    points, return_distance=True, all_matches=False
                )
                j = int(np.argmin(dist))
                if best is None or dist[j] < best[0]:
                    best = (float(dist[j]), i, component[int(src[j])], main[int(dst[j])])
            dist, i, a, b = best
            self.add_line([self.xy[a], self.xy[b]], bridge=True)
            self.bridged_m += dist
            main = main + rest.pop(i)

    def shortest_path(
        self,
        source: int,
        target: int | None,
        directed: bool = True,
    ) -> tuple[list[int] | None, dict[int, float]]:
        """Dijkstra. With target None, returns distances to every reachable node."""
        dist = {source: 0.0}
        prev: dict[int, int] = {}
        heap = [(0.0, source)]
        while heap:
            d, node = heapq.heappop(heap)
            if d > dist[node]:
                continue
            if node == target:
                break
            if directed:
                edges = self.out[node].items()
            else:
                edges = ((n, self._undirected_edge(node, n)) for n in self.neighbours[node])
            for nbr, (length, _edge) in edges:
                nd = d + length
                if nd < dist.get(nbr, math.inf):
                    dist[nbr] = nd
                    prev[nbr] = node
                    heapq.heappush(heap, (nd, nbr))
        if target is None or target not in dist:
            return None, dist
        path = [target]
        while path[-1] != source:
            path.append(prev[path[-1]])
        return path[::-1], dist

    def _undirected_edge(self, a: int, b: int) -> tuple[float, int]:
        edge = self._edge_ids[(min(a, b), max(a, b))]
        return self.edge_length[edge], edge

    def path_edges(self, path: list[int]) -> list[int]:
        return [self._undirected_edge(a, b)[1] for a, b in zip(path, path[1:], strict=False)]

    def nearest_node(self, xy: XY, candidates: list[int] | None = None) -> tuple[int, float]:
        nodes = candidates if candidates is not None else range(len(self.xy))
        return min(((n, math.dist(xy, self.xy[n])) for n in nodes), key=lambda item: item[1])


@dataclass
class Anchor:
    """Where a terminal named in the route name actually is."""

    label: str
    xy: XY


def find_anchor(place: str, own: list[Anchor], gazetteer: list[Anchor], graph: PieceGraph):
    """Best point for a place name: the route's own points first, then every KML point.

    Ties are broken by closeness to one of the route's dead ends, so "Dago" picks
    "Terminal Dago" over "Simpang Dago" when the route ends at the terminal.
    """
    ends = graph.leaves or list(range(len(graph.xy)))
    for pool in (own, gazetteer):
        best = None
        for anchor in pool:
            score = name_score(place, anchor.label)
            if not score:
                continue
            _, to_route = graph.nearest_node(anchor.xy)
            if to_route > MAX_ANCHOR_DISTANCE_M:
                continue
            _, to_end = graph.nearest_node(anchor.xy, ends)
            key = (-score, to_end)
            if best is None or key < best[0]:
                best = (key, anchor)
        if best:
            return best[1]
    return None


def _end_node(graph: PieceGraph, anchor: Anchor) -> int:
    leaves = graph.leaves
    if leaves:
        leaf, dist = graph.nearest_node(anchor.xy, leaves)
        if dist <= LEAF_SNAP_M:
            return leaf
    return graph.nearest_node(anchor.xy)[0]


def _farthest(graph: PieceGraph, source: int, candidates: list[int]) -> int:
    _, dist = graph.shortest_path(source, None, directed=False)
    reachable = [n for n in candidates if n in dist and n != source] or list(dist)
    return max(reachable, key=lambda n: dist[n])


@dataclass
class OrderedLine:
    coords: list[XY]
    coverage: float
    bridged_gap_m: float
    oneway_relaxed: bool
    is_loop: bool
    orientation: str


@dataclass
class _Chain:
    """A run of vertices between junctions, so the trail search works on few, long edges."""

    nodes: list[int]
    gain: float  # metres of delivered pieces covered; bridges count against
    forward: bool
    backward: bool


def _chains(graph: PieceGraph, keep: set[int]) -> list[_Chain]:
    junctions = {n for n, nbrs in enumerate(graph.neighbours) if len(nbrs) != 2} | keep
    seen_edges: set[int] = set()
    chains = []
    for start in junctions:
        for first in graph.neighbours[start]:
            if graph._undirected_edge(start, first)[1] in seen_edges:
                continue
            nodes = [start, first]
            while nodes[-1] not in junctions:
                prev, cur = nodes[-2], nodes[-1]
                nodes.append(next(n for n in graph.neighbours[cur] if n != prev))
            edges = graph.path_edges(nodes)
            seen_edges.update(edges)
            chains.append(
                _Chain(
                    nodes=nodes,
                    gain=sum(
                        -graph.edge_length[e] if graph.edge_is_bridge[e] else graph.edge_length[e]
                        for e in edges
                    ),
                    forward=all(b in graph.out[a] for a, b in zip(nodes, nodes[1:], strict=False)),
                    backward=all(a in graph.out[b] for a, b in zip(nodes, nodes[1:], strict=False)),
                )
            )
    return chains


def longest_trail(
    graph: PieceGraph, start: int, end: int, directed: bool = True, budget: int = 50_000
) -> list[int] | None:
    """Path from start to end using each piece at most once and covering as much as possible.

    A shortest path would cut off loops the vehicle really drives (round a market, through
    a one-way system), so this searches for the longest trail instead. Branch and bound
    over junction-to-junction chains; gives up after `budget` steps with the best so far.
    """
    chains = _chains(graph, {start, end})
    if not directed:
        for chain in chains:
            chain.forward = chain.backward = True
    exits: dict[int, list[tuple[int, bool]]] = {}
    for i, chain in enumerate(chains):
        if chain.forward:
            exits.setdefault(chain.nodes[0], []).append((i, True))
        if chain.backward:
            exits.setdefault(chain.nodes[-1], []).append((i, False))
    for options in exits.values():
        options.sort(key=lambda option: -chains[option[0]].gain)

    used = [False] * len(chains)
    trail: list[tuple[int, bool]] = []
    best: tuple[float, list[tuple[int, bool]] | None] = (-math.inf, None)
    steps = 0
    # (node, gain so far, gain still available, index into exits[node])
    stack = [(start, 0.0, sum(max(c.gain, 0.0) for c in chains), 0)]
    while stack and steps < budget:
        node, gain, remaining, i = stack.pop()
        if i == 0:
            steps += 1
            if node == end and trail and gain > best[0]:
                best = (gain, list(trail))
        options = exits.get(node, [])
        while i < len(options) and used[options[i][0]]:
            i += 1
        if i == len(options) or gain + remaining <= best[0]:
            if trail:
                used[trail.pop()[0]] = False
            continue
        chain_index, forward = options[i]
        chain = chains[chain_index]
        stack.append((node, gain, remaining, i + 1))
        used[chain_index] = True
        trail.append((chain_index, forward))
        nxt = chain.nodes[-1] if forward else chain.nodes[0]
        stack.append((nxt, gain + chain.gain, remaining - max(chain.gain, 0.0), 0))

    if best[1] is None:
        return None
    path = [start]
    for chain_index, forward in best[1]:
        nodes = chains[chain_index].nodes
        path.extend((nodes if forward else nodes[::-1])[1:])
    return path


def order_pieces(
    pieces: list[list[XY]],
    oneways: list[str],
    origin: Anchor | None,
    destination: Anchor | None,
    loop: bool = False,
) -> OrderedLine:
    graph = PieceGraph()
    for coords, oneway in zip(pieces, oneways, strict=True):
        graph.add_line(coords, oneway)
    graph.bridge_gaps()

    leaves = graph.leaves
    if loop:
        start = _end_node(graph, origin) if origin else (leaves or [0])[0]
        end = start
        orientation = "loop"
    elif len(leaves) == 2 and (origin or destination):
        # A clean line with two dead ends: the names only have to say which end is which.
        a, b = (graph.xy[leaf] for leaf in leaves)

        def cost(o: XY, d: XY) -> float:
            return (math.dist(origin.xy, o) if origin else 0) + (
                math.dist(destination.xy, d) if destination else 0
            )

        start, end = leaves if cost(a, b) <= cost(b, a) else leaves[::-1]
        orientation = "names" if origin and destination else "one-name"
    elif origin and destination:
        start, end = _end_node(graph, origin), _end_node(graph, destination)
        orientation = "names"
    elif origin:
        start = _end_node(graph, origin)
        end = _farthest(graph, start, leaves)
        orientation = "one-name"
    elif destination:
        end = _end_node(graph, destination)
        start = _farthest(graph, end, leaves)
        orientation = "one-name"
    else:
        # No names to go by: take the two dead ends furthest apart. Direction is a guess.
        start = _farthest(graph, (leaves or [0])[0], leaves)
        end = _farthest(graph, start, leaves)
        orientation = "guess"

    is_loop = loop or math.dist(graph.xy[start], graph.xy[end]) < LOOP_M
    candidates: list[tuple[list[int], bool]] = []
    path = longest_trail(graph, start, end)
    if path is not None:
        candidates.append((path, False))
    if start == end:
        # A lasso (out along a road, round a loop, back the same road) is not a trail:
        # also try the longest trail out to the farthest point and the shortest way back.
        turn = _farthest(graph, start, list(range(len(graph.xy))))
        out = longest_trail(graph, start, turn)
        back, _ = graph.shortest_path(turn, start)
        relaxed = out is None or back is None
        out = out or graph.shortest_path(start, turn, directed=False)[0]
        back = back or graph.shortest_path(turn, start, directed=False)[0]
        candidates.append((out + back[1:], relaxed))
    if not candidates:
        candidates.append((longest_trail(graph, start, end, directed=False), True))

    total = sum(length for e, length in enumerate(graph.edge_length) if not graph.edge_is_bridge[e])

    def covered(path: list[int]) -> float:
        edges = set(graph.path_edges(path))
        return sum(graph.edge_length[e] for e in edges if not graph.edge_is_bridge[e])

    path, relaxed = max(candidates, key=lambda candidate: covered(candidate[0]))
    bridged = sum(
        graph.edge_length[e] for e in set(graph.path_edges(path)) if graph.edge_is_bridge[e]
    )
    return OrderedLine(
        coords=[graph.xy[n] for n in path],
        coverage=covered(path) / total if total else 0.0,
        bridged_gap_m=bridged,
        oneway_relaxed=relaxed,
        is_loop=is_loop,
        orientation=orientation,
    )


@dataclass
class StopOut:
    name: str
    measure_m: float
    xy: XY
    is_virtual: bool


def place_stops(
    line: LineString,
    points: list[tuple[str, XY]],
    service: ServiceProfile,
    origin_name: str,
    destination_name: str,
    street_names: list[tuple[str, LineString]],
) -> list[StopOut]:
    """Boarding points along the ordered line, in travel order."""
    stops: list[StopOut] = []
    for label, xy in points:
        if line.distance(Point(xy)) <= MAX_STOP_OFFSET_M:
            measure = line.project(Point(xy))
            stops.append(StopOut(label, measure, _xy(line.interpolate(measure)), False))

    trust_points = service.boarding == Boarding.STOPS and len(stops) >= MIN_POINTS_FOR_STOP_LIST
    if not trust_points:
        spacing = service.stop_spacing_m
        count = max(1, round(line.length / spacing))
        for i in range(1, count):
            measure = line.length * i / count
            xy = _xy(line.interpolate(measure))
            stops.append(StopOut(_street_name(xy, street_names), measure, xy, True))

    # Make sure both ends are boardable.
    for measure, label in ((0.0, origin_name), (line.length, destination_name)):
        if not any(abs(stop.measure_m - measure) < MAX_STOP_OFFSET_M for stop in stops):
            stops.append(StopOut(label, measure, _xy(line.interpolate(measure)), False))

    stops.sort(key=lambda stop: (stop.measure_m, stop.is_virtual))
    deduped: list[StopOut] = []
    for stop in stops:
        if deduped and stop.measure_m - deduped[-1].measure_m < 30:
            continue
        deduped.append(stop)
    return deduped


def _xy(point: Point) -> XY:
    return (point.x, point.y)


def _street_name(xy: XY, street_names: list[tuple[str, LineString]]) -> str:
    if not street_names:
        return "Along the route"
    name, _ = min(street_names, key=lambda item: item[1].distance(Point(xy)))
    return name or "Along the route"


@dataclass
class TransformedRoute:
    name: str
    code: str
    origin_name: str
    destination_name: str
    mode: Mode
    color: str
    source: str
    files: list[str]
    service: ServiceProfile
    line: list[tuple[float, float]]
    length_m: float
    ordered: OrderedLine
    stops: list[tuple[StopOut, tuple[float, float]]]
    pieces: list[RawPiece] = field(default_factory=list)


def build_gazetteer(routes: list[RawRoute]) -> list[Anchor]:
    seen, anchors = set(), []
    for route in routes:
        for point in route.points:
            key = (point.name, round(point.lon, 4), round(point.lat, 4))
            if key not in seen:
                seen.add(key)
                anchors.append(Anchor(point.name, to_metric([(point.lon, point.lat)])[0]))
    return anchors


def _anchors(points: list[RawPoint]) -> list[Anchor]:
    if not points:
        return []
    xys = to_metric([(p.lon, p.lat) for p in points])
    return [Anchor(p.name, xy) for p, xy in zip(points, xys, strict=True)]


def transform_route(
    raw: RawRoute, gazetteer: list[Anchor], profiles: dict | None = None
) -> TransformedRoute:
    parsed = parse_route_name(raw.name)
    mode = classify_mode(raw.name)
    service = service_for(raw.name, mode, profiles)

    pieces = [to_metric(piece.coords) for piece in raw.pieces]
    own = _anchors(raw.points)

    # Graph built once just for anchor matching; order_pieces builds its own.
    probe = PieceGraph()
    for coords in pieces:
        probe.add_line(coords)
    origin = find_anchor(parsed.origin, own, gazetteer, probe)
    destination = None
    if parsed.destination != parsed.origin:
        destination = find_anchor(parsed.destination, own, gazetteer, probe)

    # "A → B (searah jarum jam)" runs clockwise round a loop; a single place is a circular
    # shuttle.
    loop = len(parsed.places) == 1 or "jarum jam" in raw.name
    if loop and origin is None and own:
        origin = own[0]
    ordered = order_pieces(
        pieces, [piece.oneway for piece in raw.pieces], origin, destination, loop=loop
    )
    line = LineString(ordered.coords)
    street_names = [
        (piece.name, LineString(coords))
        for piece, coords in zip(raw.pieces, pieces, strict=True)
        if piece.name
    ]
    stops = place_stops(
        line,
        [(anchor.label, anchor.xy) for anchor in own],
        service,
        parsed.origin,
        parsed.destination,
        street_names,
    )
    stop_lonlat = to_lonlat([stop.xy for stop in stops])
    return TransformedRoute(
        name=raw.name,
        code=parsed.code,
        origin_name=parsed.origin,
        destination_name=parsed.destination,
        mode=mode,
        color=raw.color or "#6B7280",
        source=raw.source,
        files=raw.files,
        service=service,
        line=to_lonlat(ordered.coords),
        length_m=line.length,
        ordered=ordered,
        stops=list(zip(stops, stop_lonlat, strict=True)),
        pieces=raw.pieces,
    )
