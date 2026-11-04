"""Run extract → transform → load and record the run with a QA report."""

from collections import Counter
from collections.abc import Callable
from pathlib import Path

from django.utils import timezone

from transit.etl import extract, load, transform
from transit.models import ImportRun

# Routes below this coverage or above this bridged distance are listed in the report.
LOW_COVERAGE = 0.85
LARGE_GAP_M = 500


def run_import(
    shp: Path | None,
    kml: Path | None,
    profiles: dict | None = None,
    log: Callable[[str], None] = print,
) -> ImportRun:
    started = timezone.now()
    shp_routes: list[extract.RawRoute] = []
    kml_routes: list[extract.RawRoute] = []
    if shp:
        with extract.source_dir(shp) as directory:
            shp_routes = extract.read_shapefiles(directory)
        log(f"Read {len(shp_routes)} routes from {shp.name}")
    if kml:
        with extract.source_dir(kml) as directory:
            kml_routes = extract.read_kml(directory)
        log(f"Read {len(kml_routes)} routes from {kml.name}")

    raw_routes = [route for route in extract.merge(shp_routes, kml_routes) if route.pieces]
    gazetteer = transform.build_gazetteer(kml_routes)
    log(f"{len(raw_routes)} distinct routes, {len(gazetteer)} named points")

    transformed = []
    for raw in raw_routes:
        transformed.append(transform.transform_route(raw, gazetteer, profiles))
    route_count, stop_count = load.replace_routes(transformed)

    report = {
        "routes_by_mode": dict(Counter(route.mode.value for route in transformed)),
        "routes_by_piece_source": dict(Counter(raw.pieces_from for raw in raw_routes)),
        "orientation": dict(Counter(route.ordered.orientation for route in transformed)),
        "loops": sum(route.ordered.is_loop for route in transformed),
        "oneway_relaxed": sorted(r.name for r in transformed if r.ordered.oneway_relaxed),
        "low_coverage": sorted(
            (r.name, round(r.ordered.coverage, 3))
            for r in transformed
            if r.ordered.coverage < LOW_COVERAGE
        ),
        "large_gaps": sorted(
            (r.name, round(r.ordered.bridged_gap_m))
            for r in transformed
            if r.ordered.bridged_gap_m > LARGE_GAP_M
        ),
        "total_length_km": round(sum(r.length_m for r in transformed) / 1000, 1),
    }
    return ImportRun.objects.create(
        started_at=started,
        finished_at=timezone.now(),
        sources=[str(path) for path in (shp, kml) if path],
        route_count=route_count,
        stop_count=stop_count,
        report=report,
    )
