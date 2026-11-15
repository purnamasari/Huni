"""Subsidized housing estates and the house types they list.

Rows are loaded from the seed files by `manage.py import_estates` (see housing/dataset.py);
edit the seed and re-import rather than editing rows. Points are stored in EPSG:4326, and
distances in `access` were measured in UTM 48S (EPSG:32748) during enrichment.
"""

from django.contrib.gis.db import models


class Region(models.TextChoices):
    GARUT = "garut", "Garut"
    BANDUNG = "bandung", "Bandung Raya"


class Precision(models.TextChoices):
    # The estate's own site.
    EXACT = "exact", "Estate site"
    # Only the village is known: the point is the village's reference point, shared by
    # every estate in that village.
    DESA = "desa", "Village reference point"


class EstateQuerySet(models.QuerySet):
    def in_reading_order(self):
        """Regions in the order they are declared (Garut first), then kecamatan and name."""
        rank = models.Case(
            *(
                models.When(region=region, then=position)
                for position, region in enumerate(Region.values)
            ),
            output_field=models.IntegerField(),
        )
        return self.annotate(region_rank=rank).order_by("region_rank", "kecamatan", "name")


class Estate(models.Model):
    objects = EstateQuerySet.as_manager()

    # Sikumbang's "ID Lokasi", e.g. GRT0920062024T002.
    source_id = models.CharField(max_length=20, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=120)
    developer = models.CharField(max_length=120, blank=True)
    association = models.CharField(max_length=40, blank=True)

    region = models.CharField(max_length=20, choices=Region.choices)
    kabupaten = models.CharField(max_length=60)
    kecamatan = models.CharField(max_length=60)
    desa = models.CharField(max_length=60)
    address = models.CharField(max_length=200, blank=True)

    location = models.PointField(srid=4326)
    location_precision = models.CharField(max_length=10, choices=Precision.choices)

    registered_year = models.PositiveSmallIntegerField(null=True, blank=True)
    # Sikumbang's counters: units still for sale, and units sold. Null when not readable.
    subsidized_available = models.PositiveIntegerField(null=True, blank=True)
    subsidized_sold = models.PositiveIntegerField(null=True, blank=True)
    commercial_available = models.PositiveIntegerField(null=True, blank=True)
    commercial_sold = models.PositiveIntegerField(null=True, blank=True)

    # What enrichment measured around `location`; see housing/etl/enrich.py for the shapes.
    access = models.JSONField(null=True, blank=True)
    flood = models.JSONField(null=True, blank=True)
    # Ratings checked on site, which replace the estimates.
    survey = models.JSONField(default=dict, blank=True)
    # Things a reader should know before trusting the row, in Indonesian.
    caveats = models.JSONField(default=list, blank=True)

    source_url = models.URLField()
    retrieved = models.DateField()

    def __str__(self):
        return f"{self.name} ({self.desa}, {self.kecamatan})"

    @property
    def units(self) -> dict | None:
        counts = {
            "subsidized_available": self.subsidized_available,
            "subsidized_sold": self.subsidized_sold,
            "commercial_available": self.commercial_available,
            "commercial_sold": self.commercial_sold,
        }
        return counts if any(value is not None for value in counts.values()) else None


class Listing(models.Model):
    """A house type an estate offers, at the price Sikumbang lists for it."""

    estate = models.ForeignKey(Estate, related_name="listings", on_delete=models.CASCADE)
    position = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=80)
    subsidized = models.BooleanField()
    price_idr = models.PositiveBigIntegerField()
    building_m2 = models.PositiveSmallIntegerField(null=True, blank=True)
    land_m2 = models.PositiveSmallIntegerField(null=True, blank=True)
    bedrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    bathrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    specs = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["estate", "position"]
        constraints = [
            models.UniqueConstraint(fields=["estate", "position"], name="listing_position_unique")
        ]

    def __str__(self):
        return f"{self.estate.name}: {self.name}"
