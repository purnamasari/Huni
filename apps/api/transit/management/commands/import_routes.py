import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from transit.etl.pipeline import run_import
from transit.models import ImportRun

SHP_NAME = "tfb-route-shp.zip"
KML_NAME = "tfb-route-kml.zip"
# A fresh download in raw/ wins over the copy committed in seed/transit/.
SOURCE_DIRS = ("raw", "seed/transit")


def default_source_dir() -> Path:
    """The first of SOURCE_DIRS (under DATA_DIR) holding either export, else raw/."""
    for name in SOURCE_DIRS:
        folder = settings.DATA_DIR / name
        if (folder / SHP_NAME).exists() or (folder / KML_NAME).exists():
            return folder
    return settings.DATA_DIR / SOURCE_DIRS[0]


class Command(BaseCommand):
    help = (
        "Import Transport for Bandung routes (shapefile and/or KML, as folders or .zip) "
        "into the transit tables, replacing what is there."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--shp",
            type=Path,
            help=f"Default: {SHP_NAME} in DATA_DIR/raw, else DATA_DIR/seed/transit",
        )
        parser.add_argument(
            "--kml",
            type=Path,
            help=f"Default: {KML_NAME} in DATA_DIR/raw, else DATA_DIR/seed/transit",
        )
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Do nothing if routes were imported before (used when the api container starts).",
        )

    def handle(self, *args, shp, kml, if_empty, **options):
        if if_empty and (last := ImportRun.objects.order_by("-finished_at").first()):
            self.stdout.write(
                f"Routes already imported ({last.route_count} routes, "
                f"{last.finished_at:%Y-%m-%d}); skipping. Run without --if-empty to re-import."
            )
            return

        folder = default_source_dir()
        shp = shp or folder / SHP_NAME
        kml = kml or folder / KML_NAME
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
