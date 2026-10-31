"""Transit routes imported from the Transport for Bandung route files.

Every route is directional: "09: Dago → Stasiun Hall" and "09: Stasiun Hall → Dago" are two
rows. Geometry is stored in EPSG:4326; anything measured in metres was computed in UTM 48S
(EPSG:32748) during the import.
"""

from django.contrib.gis.db import models


class Mode(models.TextChoices):
    ANGKOT = "angkot", "Angkot"
    MINIBUS = "minibus", "Minibus (Elf)"
    BUS = "bus", "Bus"
    FEEDER = "feeder", "Feeder bus"
    SHUTTLE = "shuttle", "Shuttle"
    RAIL = "rail", "Commuter rail"


class Boarding(models.TextChoices):
    # Angkot and Elf stop wherever a passenger waves them down.
    HAIL = "hail", "Hail anywhere along the route"
    STOPS = "stops", "Fixed stops only"


class ImportRun(models.Model):
    """One run of the route ETL, with the QA report it produced."""

    started_at = models.DateTimeField()
    finished_at = models.DateTimeField()
    sources = models.JSONField(default=list)
    route_count = models.PositiveIntegerField(default=0)
    stop_count = models.PositiveIntegerField(default=0)
    report = models.JSONField(default=dict)

    def __str__(self):
        return f"Import {self.pk} at {self.finished_at:%Y-%m-%d %H:%M}"


class Route(models.Model):
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=40, blank=True)
    origin_name = models.CharField(max_length=120)
    destination_name = models.CharField(max_length=120)
    mode = models.CharField(max_length=20, choices=Mode.choices)
    color = models.CharField(max_length=7, default="#6B7280")
    source = models.CharField(max_length=120)
    source_files = models.JSONField(default=list)

    # Ordered in the direction of travel, rebuilt from unordered way pieces.
    geom = models.LineStringField(srid=4326)
    length_m = models.FloatField()

    # QA from ordering the pieces (see transit.etl.transform).
    coverage = models.FloatField(help_text="Share of the delivered pieces the ordered line uses")
    bridged_gap_m = models.FloatField(default=0)
    oneway_relaxed = models.BooleanField(default=False)
    is_loop = models.BooleanField(default=False)
    orientation = models.CharField(max_length=20)

    # Service attributes. Defaults come from service_profiles.json and are placeholders
    # until real fares/frequencies are known; service_is_placeholder says which is which.
    boarding = models.CharField(max_length=10, choices=Boarding.choices)
    fare_base_idr = models.PositiveIntegerField()
    fare_per_km_idr = models.PositiveIntegerField(default=0)
    fare_max_idr = models.PositiveIntegerField(null=True, blank=True)
    avg_speed_kmh = models.FloatField()
    headway_min = models.FloatField()
    service_start = models.TimeField()
    service_end = models.TimeField()
    service_is_placeholder = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RouteStop(models.Model):
    """A place to board or alight. Virtual stops are generated along hail-anywhere routes."""

    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    sequence = models.PositiveIntegerField()
    name = models.CharField(max_length=200)
    measure_m = models.FloatField(help_text="Distance along the route geometry")
    geom = models.PointField(srid=4326)
    is_virtual = models.BooleanField(default=False)

    class Meta:
        ordering = ["route", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["route", "sequence"], name="unique_stop_sequence")
        ]

    def __str__(self):
        return f"{self.route.name} #{self.sequence} {self.name}"


class RouteSegment(models.Model):
    """A way piece exactly as delivered (OSM way for shapefiles), kept for traceability."""

    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="segments")
    osm_way_id = models.BigIntegerField(null=True, blank=True)
    name = models.CharField(max_length=200, blank=True)
    highway = models.CharField(max_length=40, blank=True)
    oneway = models.CharField(max_length=10, blank=True)
    geom = models.LineStringField(srid=4326)
