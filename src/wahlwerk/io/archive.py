"""Reading election bundles from the wahlwerk-data archive.

The engine does not depend on the archive. Nothing here is needed to run the test suite,
and every function raises a message naming the places it looked rather than failing
obscurely when the archive is absent.

An election id maps to a path by splitting on its **last dot**: everything before it is
the jurisdiction and becomes a directory, the last segment is the election. So
``de.bund.2025`` lives at ``elections/de.bund/2025``, and ``de.nw.koeln.2025`` at
``elections/de.nw.koeln/2025``. The archive defines the same mapping on its side; it is
written down in both because it is the one thing the two repositories must agree on.

Resolution order for the archive root, first hit wins::

    $WAHLWERK_DATA              explicit -- what CI and containers set
    ../wahlwerk-data            a sibling clone, searched upwards from the cwd
    ~/.cache/wahlwerk/data      fetched

The sibling clone is the zero-config path, never a requirement.
"""

from __future__ import annotations

import csv
import os
import tomllib
from datetime import date
from pathlib import Path

from wahlwerk.ids import BodyId, LevelName, PartyId, UnitId
from wahlwerk.mandate import Mandate, MandateSource
from wahlwerk.model import Count, Model, Seats
from wahlwerk.state.chamber import Chamber, Term

__all__ = [
    "ARCHIVE_ENV",
    "SCHEMA_SUPPORTED",
    "ArchiveNotFound",
    "Bundle",
    "DeclaredSeats",
    "available",
    "bundle_path",
    "find_archive",
    "load_chamber",
    "read_bundle",
]

ARCHIVE_ENV = "WAHLWERK_DATA"
SIBLING = "wahlwerk-data"
CACHE = Path.home() / ".cache" / "wahlwerk" / "data"

SCHEMA_SUPPORTED = frozenset({1})
"""Bundle schema versions this engine can read. A bundle outside the set is refused --
a format change must break loudly rather than mis-parse quietly."""


class ArchiveNotFound(LookupError):
    """Raised when no archive root can be resolved, naming everywhere that was tried."""

    def __init__(self, tried: tuple[Path, ...]) -> None:
        super().__init__(
            "no wahlwerk-data archive found. Tried:\n  "
            + "\n  ".join(str(p) for p in tried)
            + f"\nSet ${ARCHIVE_ENV}, clone {SIBLING} beside this repository, "
            "or run scripts/fetch_data.py."
        )
        self.tried = tried


def candidate_roots() -> tuple[Path, ...]:
    """Every place an archive is looked for, in order."""
    found: list[Path] = []
    env = os.environ.get(ARCHIVE_ENV)
    if env:
        found.append(Path(env))
    here = Path.cwd().resolve()
    found.extend(parent / SIBLING for parent in (here, *here.parents))
    # An editable checkout: src/wahlwerk/io/archive.py -> repo -> its parent directory.
    package_repo = Path(__file__).resolve().parents[3]
    found.append(package_repo.parent / SIBLING)
    found.append(CACHE)
    return tuple(dict.fromkeys(found))  # de-duplicated, order preserved


def find_archive(root: Path | None = None) -> Path:
    """The directory holding election bundles.

    Accepts either a checkout of wahlwerk-data or its ``elections/`` directory directly,
    so ``WAHLWERK_DATA`` can point at whichever the caller finds natural.
    """
    candidates = (root,) if root is not None else candidate_roots()
    tried: list[Path] = []
    for candidate in candidates:
        tried.append(candidate)
        elections = candidate / "elections"
        if elections.is_dir():
            return elections
        if candidate.is_dir() and any(candidate.glob("*/*/election.toml")):
            return candidate
    raise ArchiveNotFound(tuple(tried))


def bundle_path(root: Path, election_id: str) -> Path:
    """``de.bund.2025`` -> ``<root>/de.bund/2025``."""
    jurisdiction, _, election = election_id.rpartition(".")
    if not jurisdiction:
        raise ValueError(
            f"election id {election_id!r} needs a jurisdiction and an election, "
            f"e.g. 'de.bund.2025'"
        )
    return root / jurisdiction / election


class DeclaredSeats(Model):
    """One row of ``declared.csv``: seats a party holds in one unit, as published."""

    unit: UnitId
    party: PartyId
    seats: Seats


class Bundle(Model):
    """One election as the archive records it.

    This is the *declared* result -- what the returning officer published. It is never
    something the engine derived, which is exactly what makes it usable as a target.
    """

    id: str
    body: BodyId
    day: date
    """Election day. Not the start of the Wahlperiode -- see :class:`Term`."""

    term: int | None = None
    seats_total: Count | None = None
    law: str | None = None
    declared: tuple[DeclaredSeats, ...] = ()
    contents: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    source: dict[str, str] = {}
    """Provenance from ``election.toml``. Carries the dl-de/by-2-0 attribution, which
    must travel with anything republished from it."""

    @property
    def national(self) -> dict[PartyId, int]:
        """Seats per party at the root unit -- the body id's jurisdiction."""
        root = UnitId(self.body.rsplit(".", 1)[0])
        return {d.party: d.seats for d in self.declared if d.unit == root}

    @property
    def by_unit(self) -> dict[UnitId, dict[PartyId, int]]:
        """Seats per party below the root unit -- Land lists, federally."""
        root = UnitId(self.body.rsplit(".", 1)[0])
        out: dict[UnitId, dict[PartyId, int]] = {}
        for row in self.declared:
            if row.unit != root:
                out.setdefault(row.unit, {})[row.party] = row.seats
        return out


def read_bundle(election_id: str, root: Path | None = None) -> Bundle:
    """Read one bundle. Raises if it is absent or its schema is one we cannot read."""
    directory = bundle_path(find_archive(root), election_id)
    manifest_path = directory / "election.toml"
    if not manifest_path.is_file():
        raise LookupError(f"no bundle for {election_id!r} at {directory}")

    with manifest_path.open("rb") as handle:
        manifest = tomllib.load(handle)

    schema = manifest.get("schema")
    if schema not in SCHEMA_SUPPORTED:
        raise ValueError(
            f"{election_id}: bundle schema {schema!r}, this engine reads "
            f"{sorted(SCHEMA_SUPPORTED)}. Update wahlwerk or pin an older data tag."
        )

    declared: tuple[DeclaredSeats, ...] = ()
    declared_path = directory / "declared.csv"
    if declared_path.is_file():
        rows = csv.DictReader(declared_path.read_text(encoding="utf-8").splitlines())
        declared = tuple(
            DeclaredSeats(
                unit=UnitId(r["unit"]), party=PartyId(r["party"]), seats=int(r["seats"])
            )
            for r in rows
        )

    return Bundle(
        id=manifest["id"],
        body=BodyId(manifest["body"]),
        day=manifest["date"],
        term=manifest.get("term"),
        seats_total=manifest.get("seats_total"),
        law=manifest.get("law"),
        declared=declared,
        contents=tuple(manifest.get("contents", ())),
        notes=tuple(manifest.get("notes", ())),
        source={k: str(v) for k, v in manifest.get("source", {}).items()},
    )


def load_chamber(election_id: str, root: Path | None = None) -> Chamber:
    """Build the chamber an election produced, from the published seat distribution.

    One :class:`~wahlwerk.mandate.Mandate` per seat, carrying the party and the unit whose
    list it came from. Nothing is derived: ``source`` is ``UNRECORDED`` because the
    published distribution says nothing per seat, and ``person`` is unset because it names
    nobody. Fabricating either is the failure this archive exists to prevent.

    The per-unit rows must sum to the national ones; a bundle where they do not is a data
    error and raises rather than producing a chamber that is quietly the wrong size.
    """
    bundle = read_bundle(election_id, root)
    if not bundle.declared:
        raise LookupError(
            f"{election_id}: bundle has no declared.csv, so there is no chamber to build "
            f"(contents: {list(bundle.contents)})"
        )

    national = bundle.national
    per_unit = bundle.by_unit
    if national:
        for party, seats in national.items():
            below = sum(u.get(party, 0) for u in per_unit.values())
            if below != seats:
                raise ValueError(
                    f"{election_id}: {party} holds {seats} seats nationally but "
                    f"{below} across units -- the bundle is inconsistent"
                )

    level = None if not per_unit else _level_of(next(iter(per_unit)))
    mandates: list[Mandate] = []
    for unit in sorted(per_unit):
        for party in sorted(per_unit[unit]):
            for _ in range(per_unit[unit][party]):
                mandates.append(
                    Mandate(
                        seat=f"{election_id}.{len(mandates) + 1:04d}",
                        party=party,
                        unit=unit,
                        level=level,
                        source=MandateSource.UNRECORDED,
                    )
                )

    if bundle.seats_total is not None and len(mandates) != bundle.seats_total:
        raise ValueError(
            f"{election_id}: built {len(mandates)} mandates but the bundle declares "
            f"{bundle.seats_total} seats"
        )

    return Chamber(
        body=bundle.body,
        term=Term(body=bundle.body, number=bundle.term, elected_on=bundle.day),
        mandates=tuple(mandates),
    )


def _level_of(unit: UnitId) -> LevelName | None:
    """``de.bund.land.01`` -> ``land``. The archive names the level in the unit id."""
    parts = unit.split(".")
    if len(parts) >= 2 and not parts[-2].isdigit():
        return LevelName(parts[-2])
    return None


def available(root: Path | None = None) -> tuple[str, ...]:
    """Every election id in the archive, sorted."""
    archive = find_archive(root)
    return tuple(
        sorted(
            f"{p.parent.name}.{p.name}"
            for p in archive.glob("*/*")
            if (p / "election.toml").is_file()
        )
    )
