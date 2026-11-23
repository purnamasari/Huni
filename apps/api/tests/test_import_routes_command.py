"""`manage.py import_routes`: where it finds the exports, and --if-empty."""

from pathlib import Path

import pytest
from django.core.management import call_command

from tests.transit_fixtures import write_network
from transit.etl import extract
from transit.etl.pipeline import run_import
from transit.management.commands.import_routes import KML_NAME, SHP_NAME, default_source_dir
from transit.models import ImportRun

SEED_DIR = Path(__file__).resolve().parents[3] / "data" / "seed" / "transit"


def test_a_fresh_download_in_raw_wins_over_the_seed(settings, tmp_path):
    settings.DATA_DIR = tmp_path
    (tmp_path / "seed" / "transit").mkdir(parents=True)
    (tmp_path / "seed" / "transit" / SHP_NAME).touch()
    assert default_source_dir() == tmp_path / "seed" / "transit"

    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / KML_NAME).touch()
    assert default_source_dir() == tmp_path / "raw"


@pytest.mark.django_db
def test_if_empty_leaves_an_existing_import_alone(settings, tmp_path, capsys):
    run_import(None, write_network(tmp_path / "kml"), log=lambda _: None)
    settings.DATA_DIR = tmp_path / "nothing-here"  # would fail if it tried to import

    call_command("import_routes", "--if-empty")

    assert ImportRun.objects.count() == 1
    assert "skipping" in capsys.readouterr().out


def test_the_committed_seed_is_readable():
    with extract.source_dir(SEED_DIR / SHP_NAME) as folder:
        assert len(extract.read_shapefiles(folder)) == 375
    with extract.source_dir(SEED_DIR / KML_NAME) as folder:
        assert len(extract.read_kml(folder)) == 385
