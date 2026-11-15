from django.core.management.base import BaseCommand

from housing.dataset import load_seed
from housing.importer import import_seed


class Command(BaseCommand):
    help = (
        "Load the estates in housing/data into the database, replacing what is there. "
        "Safe to run again: estates are matched on their Sikumbang ID."
    )

    def handle(self, *args, **options):
        stats = import_seed(load_seed())
        if stats["without_context"]:
            self.stderr.write(
                self.style.WARNING(
                    f"{stats['without_context']} estates have no access or flood measurements "
                    "yet; run enrich_estates."
                )
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {stats['estates']} estates with {stats['listings']} house types"
                + (f", removed {stats['removed']}" if stats["removed"] else "")
            )
        )
