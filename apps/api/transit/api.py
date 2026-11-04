import json
from datetime import datetime
from typing import Literal

from django.contrib.gis.db.models.functions import AsGeoJSON, GeoFunc
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, Query, Router, Schema, Status

from transit.models import ImportRun, Mode, Route, RouteStop
from transit.routing.network import get_network
from transit.routing.planner import Option, Place, plan, travel_times

router = Router(tags=["transit"])

PLACEHOLDER_NOTE = (
    "Fares, speeds, frequencies and service hours are per-mode placeholders "
    "(apps/api/transit/service_profiles.json) until real operator data is added."
)


class Simplify(GeoFunc):
    function = "ST_SimplifyPreserveTopology"
    geom_param_pos = (0,)

    @property
    def output_field(self):
        return self.source_expressions[0].output_field


# --- Routes -----------------------------------------------------------------------------


@router.get("/routes", response=dict)
def route_collection(request, mode: Mode | None = None):
    """Every route as a GeoJSON FeatureCollection, simplified to roughly 10 m for display."""
    routes = Route.objects.annotate(geojson=AsGeoJSON(Simplify("geom", 0.0001), precision=5)).only(
        "id", "name", "code", "mode", "color"
    )
    if mode:
        routes = routes.filter(mode=mode)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": route.id,
                "geometry": json.loads(route.geojson),
                "properties": {
                    "id": route.id,
                    "name": route.name,
                    "code": route.code,
                    "mode": route.mode,
                    "color": route.color,
                },
            }
            for route in routes
        ],
    }


class StopOut(Schema):
    sequence: int
    name: str
    lon: float
    lat: float
    measure_m: float
    is_virtual: bool


class RouteDetailOut(Schema):
    id: int
    name: str
    code: str
    mode: str
    color: str
    origin_name: str
    destination_name: str
    source: str
    source_files: list[str]
    length_m: float
    coverage: float
    bridged_gap_m: float
    oneway_relaxed: bool
    is_loop: bool
    orientation: str
    boarding: str
    fare_base_idr: int
    fare_per_km_idr: int
    fare_max_idr: int | None
    avg_speed_kmh: float
    headway_min: float
    service_start: str
    service_end: str
    service_is_placeholder: bool
    stops: list[StopOut]


@router.get("/routes/{route_id}", response=RouteDetailOut)
def route_detail(request, route_id: int):
    route = get_object_or_404(Route, pk=route_id)
    stops = [
        StopOut(
            sequence=stop.sequence,
            name=stop.name,
            lon=stop.geom.x,
            lat=stop.geom.y,
            measure_m=stop.measure_m,
            is_virtual=stop.is_virtual,
        )
        for stop in route.stops.all()
    ]
    return RouteDetailOut(
        **{
            name: getattr(route, name)
            for name in RouteDetailOut.model_fields
            if name not in {"stops", "service_start", "service_end"}
        },
        service_start=route.service_start.strftime("%H:%M"),
        service_end=route.service_end.strftime("%H:%M"),
        stops=stops,
    )


# --- Places -----------------------------------------------------------------------------


class PlaceOut(Schema):
    name: str
    lon: float
    lat: float


@router.get("/places", response=list[PlaceOut])
def search_places(request, q: str = Query(..., min_length=2), limit: int = 10):
    """Named stops and terminals matching q. A stand-in until there is a real geocoder."""
    seen, places = set(), []
    stops = RouteStop.objects.filter(is_virtual=False, name__icontains=q).order_by("name", "id")
    for stop in stops.iterator():
        if stop.name in seen:
            continue
        seen.add(stop.name)
        places.append(PlaceOut(name=stop.name, lon=stop.geom.x, lat=stop.geom.y))
        if len(places) >= min(limit, 50):
            break
    return places


# --- Import QA --------------------------------------------------------------------------


class ImportRunOut(Schema):
    id: int
    finished_at: datetime
    sources: list[str]
    route_count: int
    stop_count: int
    report: dict


@router.get("/imports/latest", response={200: ImportRunOut, 404: dict})
def latest_import(request):
    run = ImportRun.objects.order_by("-id").first()
    if run is None:
        return Status(404, {"detail": "No routes imported yet. Run manage.py import_routes."})
    return run


# --- Trip planning ----------------------------------------------------------------------


class PointIn(Schema):
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)
    name: str = ""


class PlanIn(Schema):
    origin: PointIn
    destinations: list[PointIn] = Field(..., min_length=1, max_length=5)
    depart_at: datetime | None = None
    sort: Literal["balanced", "time", "cost", "availability"] = "balanced"
    max_options: int = Field(5, ge=1, le=8)


class RouteRef(Schema):
    id: int
    name: str
    code: str
    mode: str
    color: str
    boarding: str
    headway_min: float
    is_placeholder: bool


class LegOut(Schema):
    mode: str
    route: RouteRef | None
    start: PlaceOut
    end: PlaceOut
    distance_m: float
    duration_min: float
    wait_min: float
    fare_idr: int
    stop_count: int
    depart_at: datetime
    arrive_at: datetime
    available: bool
    geometry: dict


class OptionOut(Schema):
    rank: int
    summary: str
    labels: list[str]
    scores: dict[str, float]
    duration_min: float
    fare_idr: int
    walk_m: float
    wait_min: float
    transfers: int
    availability: float
    uses_placeholder: bool
    found_by: list[str]
    depart_at: datetime
    arrive_at: datetime
    legs: list[LegOut]


class SegmentOut(Schema):
    origin: PlaceOut
    destination: PlaceOut
    options: list[OptionOut]


class PlanOut(Schema):
    depart_at: datetime
    network_version: int
    segments: list[SegmentOut]
    notes: list[str]


@router.post("/plan", response=PlanOut)
def plan_trip(request, payload: PlanIn):
    """Options for each hop of origin → destination 1 → destination 2 …, ranked by `sort`.

    Each hop departs when the top-ranked option of the previous hop arrives.
    """
    net = get_network()
    depart_at = _local(payload.depart_at)

    points = [payload.origin, *payload.destinations]
    places = [
        Place(p.lon, p.lat, p.name or ("Origin" if i == 0 else f"Destination {i}"))
        for i, p in enumerate(points)
    ]
    segments, notes, clock = [], [], depart_at
    for start, end in zip(places, places[1:], strict=False):
        options = plan(net, start, end, clock, payload.sort, payload.max_options)
        if not options:
            notes.append(f"No route found from {start.name} to {end.name}.")
        segments.append(
            SegmentOut(
                origin=_place(start),
                destination=_place(end),
                options=[_option(net, option, i + 1) for i, option in enumerate(options)],
            )
        )
        if options:
            clock = options[0].arrive_at
    if any(option.uses_placeholder for s in segments for option in s.options):
        notes.append(PLACEHOLDER_NOTE)
    return PlanOut(depart_at=depart_at, network_version=net.version, segments=segments, notes=notes)


def _place(place: Place) -> PlaceOut:
    return PlaceOut(name=place.name, lon=place.lon, lat=place.lat)


def _option(net, option: Option, rank: int) -> OptionOut:
    legs = []
    for leg in option.legs:
        route = net.routes[leg.route] if leg.route is not None else None
        legs.append(
            LegOut(
                mode=leg.mode,
                route=RouteRef(
                    id=route.id,
                    name=route.name,
                    code=route.code,
                    mode=route.mode,
                    color=route.color,
                    boarding=route.boarding,
                    headway_min=route.headway_min,
                    is_placeholder=route.is_placeholder,
                )
                if route
                else None,
                start=_place(leg.from_place),
                end=_place(leg.to_place),
                distance_m=round(leg.distance_m),
                duration_min=round(leg.duration_s / 60, 1),
                wait_min=round(leg.wait_s / 60, 1),
                fare_idr=leg.fare_idr,
                stop_count=leg.stop_count,
                depart_at=leg.depart_at,
                arrive_at=leg.arrive_at,
                available=leg.available,
                geometry={"type": "LineString", "coordinates": leg.coords},
            )
        )
    rides = [leg.route for leg in legs if leg.route]
    summary = " → ".join(f"{_mode_label(r.mode)} {r.code or r.name}" for r in rides) or "Walk"
    return OptionOut(
        rank=rank,
        summary=summary,
        labels=option.labels,
        scores={key: round(value, 3) for key, value in option.scores.items()},
        duration_min=round(option.duration_s / 60, 1),
        fare_idr=option.fare_idr,
        walk_m=round(option.walk_m),
        wait_min=round(option.wait_s / 60, 1),
        transfers=option.transfers,
        availability=round(option.availability, 3),
        uses_placeholder=option.uses_placeholder,
        found_by=sorted(option.found_by),
        depart_at=option.depart_at,
        arrive_at=option.arrive_at,
        legs=legs,
    )


def _mode_label(mode: str) -> str:
    return Mode(mode).label


# --- Commute times ----------------------------------------------------------------------


class CommuteOrigin(Schema):
    id: str
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)


class CommuteIn(Schema):
    destination: PointIn
    origins: list[CommuteOrigin] = Field(..., min_length=1, max_length=1000)
    depart_at: datetime | None = None


class CommuteTimeOut(Schema):
    id: str
    minutes: float | None
    transfers: int | None
    walk_only: bool


class CommuteOut(Schema):
    depart_at: datetime
    network_version: int
    times: list[CommuteTimeOut]


@router.post("/commute", response=CommuteOut)
def commute_times(request, payload: CommuteIn):
    """Fastest travel time from each origin (e.g. every neighbourhood) to one destination.

    `minutes` is null when nothing reaches the destination within 2.5 hours at that time.
    """
    net = get_network()
    depart_at = _local(payload.depart_at)
    destination = Place(payload.destination.lon, payload.destination.lat, payload.destination.name)
    origins = [Place(o.lon, o.lat) for o in payload.origins]
    times = travel_times(net, destination, origins, depart_at)
    return CommuteOut(
        depart_at=depart_at,
        network_version=net.version,
        times=[
            CommuteTimeOut(
                id=origin.id,
                minutes=round(time.minutes, 1) if time else None,
                transfers=time.transfers if time else None,
                walk_only=bool(time and time.walk_only),
            )
            for origin, time in zip(payload.origins, times, strict=True)
        ],
    )


def _local(value: datetime | None) -> datetime:
    value = value or timezone.localtime()
    if timezone.is_naive(value):
        value = timezone.make_aware(value)
    return timezone.localtime(value)
