import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from transit.etl.pipeline import run_import

DEFAULT_SHP = "raw/tfb-route-shp.zip"
DEFAULT_KML = "raw/tfb-route-kml.zip"


class Command(BaseCommand):
    help = (
        "Import Transport for Bandung routes (shapefile and/or KML, as folders or .zip) "
        "into the transit tables, replacing what is there."
    )

    def add_arguments(self, parser):
        parser.add_argument("--shp", type=Path, help=f"Default: DATA_DIR/{DEFAULT_SHP}")
        parser.add_argument("--kml", type=Path, help=f"Default: DATA_DIR/{DEFAULT_KML}")

    def handle(self, *args, shp, kml, **options):
        shp = shp or settings.DATA_DIR / DEFAULT_SHP
        kml = kml or settings.DATA_DIR / DEFAULT_KML
        sources = [path for path in (shp, kml) if path.exists()]
        if not sources:
            raise CommandError(f"Neither {shp} nor {kml} exists. See data/README.md.")
        for path in (shp, kml):
            if not path.exists():
                self.stderr.write(self.style.WARNING(f"Skipping missing {path}"))

        run = run_import(
            shp if shp.exists() else None,
            kml if kml.exists() else None,
            log=self.stdout.write,
        )
        self.stdout.write(json.dumps(run.report, indent=2, ensure_ascii=False))
        self.stdout.write(
            self.style.SUCCESS(f"Imported {run.route_count} routes and {run.stop_count} stops")
        )
