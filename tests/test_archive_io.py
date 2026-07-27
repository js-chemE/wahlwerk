"""Reading bundles, without requiring the archive to be installed.

Everything here builds a synthetic bundle in a tmp_path, so the engine's test suite never
depends on wahlwerk-data being cloned. The real archive is exercised on the other side,
in wahlwerk-data's own tests, which have the bundles by definition.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wahlwerk.io import ArchiveNotFound, available, bundle_path, load_chamber, read_bundle
from wahlwerk.mandate import MandateSource
from wahlwerk.state import Chamber

MANIFEST = """\
schema = 1
id = "de.bund.2025"
body = "de.bund.bundestag"
date = 2025-02-23
term = 21
seats_total = 6

contents = ["declared.csv"]

notes = [
  "A note that must not end up inside [source].",
]

[source]
publisher = "Die Bundeswahlleiterin"
licence = "dl-de/by-2-0"
attribution = "© Die Bundeswahlleiterin, 2026"
"""

DECLARED = """\
unit,party,seats
de.bund,cdu,4
de.bund,spd,2
de.bund.land.01,cdu,1
de.bund.land.01,spd,2
de.bund.land.02,cdu,3
"""


@pytest.fixture
def archive(tmp_path: Path) -> Path:
    bundle = tmp_path / "elections" / "de.bund" / "2025"
    bundle.mkdir(parents=True)
    (bundle / "election.toml").write_text(MANIFEST, encoding="utf-8")
    (bundle / "declared.csv").write_text(DECLARED, encoding="utf-8")
    return tmp_path


def test_an_id_maps_to_a_path_by_its_last_dot() -> None:
    root = Path("/archive")
    assert bundle_path(root, "de.bund.2025") == root / "de.bund" / "2025"
    assert bundle_path(root, "de.by.2023") == root / "de.by" / "2023"
    assert bundle_path(root, "de.nw.koeln.2025") == root / "de.nw.koeln" / "2025"


def test_an_id_without_a_jurisdiction_is_refused() -> None:
    with pytest.raises(ValueError, match="needs a jurisdiction"):
        bundle_path(Path("/archive"), "2025")


def test_a_missing_archive_names_everywhere_it_looked(tmp_path: Path) -> None:
    with pytest.raises(ArchiveNotFound) as excinfo:
        read_bundle("de.bund.2025", root=tmp_path / "nowhere")
    assert "WAHLWERK_DATA" in str(excinfo.value)
    assert excinfo.value.tried


def test_a_bundle_carries_its_attribution(archive: Path) -> None:
    """dl-de/by-2-0 requires it, so it must survive the read."""
    bundle = read_bundle("de.bund.2025", root=archive)
    assert bundle.source["licence"] == "dl-de/by-2-0"
    assert "Bundeswahlleiterin" in bundle.source["attribution"]


def test_notes_survive_as_notes(archive: Path) -> None:
    assert read_bundle("de.bund.2025", root=archive).notes == (
        "A note that must not end up inside [source].",
    )


def test_a_schema_the_engine_cannot_read_is_refused(archive: Path) -> None:
    path = archive / "elections" / "de.bund" / "2025" / "election.toml"
    path.write_text(MANIFEST.replace("schema = 1", "schema = 99"), encoding="utf-8")
    with pytest.raises(ValueError, match="schema 99"):
        read_bundle("de.bund.2025", root=archive)


def test_a_chamber_is_one_mandate_per_seat(archive: Path) -> None:
    chamber = load_chamber("de.bund.2025", root=archive)
    assert chamber.size == 6
    assert chamber.seats_by_party == {"cdu": 4, "spd": 2}


def test_mandates_carry_the_unit_their_list_came_from(archive: Path) -> None:
    chamber = load_chamber("de.bund.2025", root=archive)
    by_unit = {m.unit for m in chamber.mandates}
    assert by_unit == {"de.bund.land.01", "de.bund.land.02"}, "national rows are the total"
    assert {m.level for m in chamber.mandates} == {"land"}


def test_nothing_is_invented(archive: Path) -> None:
    chamber = load_chamber("de.bund.2025", root=archive)
    assert {m.source for m in chamber.mandates} == {MandateSource.UNRECORDED}
    assert all(m.person is None for m in chamber.mandates)


def test_the_term_records_the_election_not_a_guessed_start(archive: Path) -> None:
    """A published seat distribution does not say when the chamber first met."""
    term = load_chamber("de.bund.2025", root=archive).term
    assert term.elected_on is not None
    assert term.number == 21
    assert term.start is None


def test_units_that_disagree_with_the_national_total_raise(archive: Path) -> None:
    path = archive / "elections" / "de.bund" / "2025" / "declared.csv"
    path.write_text(DECLARED.replace("de.bund.land.02,cdu,3", "de.bund.land.02,cdu,2"))
    with pytest.raises(ValueError, match="cdu holds 4 seats nationally but 3"):
        load_chamber("de.bund.2025", root=archive)


def test_a_seat_count_that_contradicts_the_manifest_raises(archive: Path) -> None:
    path = archive / "elections" / "de.bund" / "2025" / "election.toml"
    path.write_text(MANIFEST.replace("seats_total = 6", "seats_total = 7"), encoding="utf-8")
    with pytest.raises(ValueError, match="built 6 mandates"):
        load_chamber("de.bund.2025", root=archive)


def test_the_classmethod_is_the_same_thing(archive: Path) -> None:
    assert Chamber.from_archive("de.bund.2025", root=archive) == load_chamber(
        "de.bund.2025", root=archive
    )


def test_available_lists_ids_not_paths(archive: Path) -> None:
    assert available(root=archive) == ("de.bund.2025",)
