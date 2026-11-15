import json

from django.core.management.base import BaseCommand, CommandError

from housing.dataset import DATA_DIR, load_seed
from housing.etl.enrich import enrich
from housing.etl.sources import SourceError, Sources


class Command(BaseCommand):
    help = (
        "Measure roads, stations and flood hazard around every location in the seed and "
        "write housing/data/context.json. Needs network access to OpenFreeMap, Photon and "
        "BNPB inaRISK. Run import_estates afterwards."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Keep what context.json already has and measure only new locations.",
        )

    def handle(self, *args, only_missing, **options):
        seed = load_seed()
        try:
            document = enrich(seed, Sources(), log=self.stdout.write, only_missing=only_missing)
        except SourceError as error:
            raise CommandError(f"{error}. Nothing was written.") from error
        path = DATA_DIR / "context.json"
        path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(f"Wrote {len(document['locations'])} locations to {path}")
        )
