"""Load: replace the transit tables with a freshly transformed set of routes."""

from django.contrib.gis.geos import LineString, Point
from django.db import transaction

from transit.etl.transform import TransformedRoute
from transit.models import Route, RouteSegment, RouteStop


@transaction.atomic
def replace_routes(routes: list[TransformedRoute]) -> tuple[int, int]:
    """Delete every route and insert these. Returns (route count, stop count)."""
    Route.objects.all().delete()
    stop_count = 0
    for item in routes:
        service = item.service
        route = Route.objects.create(
            name=item.name,
            code=item.code,
            origin_name=item.origin_name,
            destination_name=item.destination_name,
            mode=item.mode,
            color=item.color,
            source=item.source,
            source_files=item.files,
            geom=LineString(item.line, srid=4326),
            length_m=item.length_m,
            coverage=item.ordered.coverage,
            bridged_gap_m=item.ordered.bridged_gap_m,
            oneway_relaxed=item.ordered.oneway_relaxed,
            is_loop=item.ordered.is_loop,
            orientation=item.ordered.orientation,
            boarding=service.boarding,
            fare_base_idr=service.fare_base_idr,
            fare_per_km_idr=service.fare_per_km_idr,
            fare_max_idr=service.fare_max_idr,
            avg_speed_kmh=service.avg_speed_kmh,
            headway_min=service.headway_min,
            service_start=service.service_start,
            service_end=service.service_end,
            service_is_placeholder=service.is_placeholder,
        )
        stops = [
            RouteStop(
                route=route,
                sequence=i,
                name=stop.name[:200],
                measure_m=stop.measure_m,
                geom=Point(lonlat, srid=4326),
                is_virtual=stop.is_virtual,
            )
            for i, (stop, lonlat) in enumerate(item.stops)
        ]
        RouteStop.objects.bulk_create(stops)
        stop_count += len(stops)
        RouteSegment.objects.bulk_create(
            RouteSegment(
                route=route,
                osm_way_id=piece.osm_way_id,
                name=piece.name[:200],
                highway=piece.highway[:40],
                oneway=piece.oneway[:10],
                geom=LineString(piece.coords, srid=4326),
            )
            for piece in item.pieces
        )
    return len(routes), stop_count
