import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from housing.models import Estate
from housing.payload import estate_payload, meta_payload

# The copy the web app bundles for when it runs without the API.
DEFAULT_OUT = settings.BASE_DIR.parent / "web" / "src" / "data" / "estates.snapshot.json"


def snapshot() -> dict:
    """What GET /api/estates returns with no filters, ready to save."""
    estates = list(Estate.objects.prefetch_related("listings").in_reading_order())
    document = {
        "meta": meta_payload(estates),
        "estates": [estate_payload(estate) for estate in estates],
    }
    # Through JSON once, so dates and the like come out the way the API sends them.
    return json.loads(json.dumps(document, default=str))


class Command(BaseCommand):
    help = "Save what GET /api/estates returns to the web app's bundled snapshot."

    def add_arguments(self, parser):
        parser.add_argument("--out", type=Path, default=DEFAULT_OUT)

    def handle(self, *args, out, **options):
        document = snapshot()
        if not document["estates"]:
            raise CommandError("No estates in the database. Run import_estates first.")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(document['estates'])} estates to {out}"))
