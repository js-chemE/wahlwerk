"""Slot 2 -- ballot structure.

How many votes a voter casts and what each vote attaches to. This is the deepest
divergence in the whole system, so the primitive is a mark that may carry a *candidate*
reference, not only a party reference:

    one vote, party-attached      BW pre-2026, many Kommunalwahlen
    two votes, party-attached     Bund, BW from 2026
    5 + 5 votes, kumuliert und
    panaschiert                   Hamburg, Bremen, most Kommunalwahlordnungen

Note the level at which the engine consumes votes. It does *not* consume individual
ballot papers: official data is published, and golden tests are written, against
aggregated counts. :class:`VoteTally` is therefore the canonical input, and it is a
flat sequence of :class:`TallyRow` -- one row per counted quantity, addressed by unit,
ballot section, and party or candidate.

That long-table shape is the whole reason the format survives contact with sixteen
Länder: cumulation is a larger ``count`` on a candidate row, panachage is rows for
several parties' candidates within one section, and a new quirk is new *rows*, never
new columns. It is also exactly one CSV file -- see :mod:`wahlwerk.io`.

:class:`BallotStructure` describes the *schema* of an admissible tally and is what a
law composes; it does not hold data.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from enum import Enum
from functools import cached_property
from typing import Protocol, runtime_checkable

from pydantic import Field, model_validator

from wahlwerk.ids import CandidateId, LevelName, PartyId, SectionName, UnitId
from wahlwerk.model import Count, Model
from wahlwerk.tiers import TierStructure

__all__ = [
    "Attachment",
    "BallotSection",
    "BallotStructure",
    "TallyKey",
    "TallyRow",
    "TurnoutRow",
    "VoteTally",
]


class Attachment(Enum):
    """What a mark in a ballot section may name."""

    PARTY = "party"
    """A closed list or a party as such (federal Zweitstimme)."""

    CANDIDATE = "candidate"
    """A person (federal Erststimme, every kumulierbar ballot)."""

    EITHER = "either"
    """Voter may mark the list as a whole *or* individual candidates
    (Hamburg Landeslistenstimmen, most Kommunalwahlordnungen)."""


class BallotSection(Model):
    """One section of the ballot paper."""

    name: SectionName
    level: LevelName
    """Tier level of the unit the section is cast in and counted at."""

    attaches_to: Attachment
    votes_per_voter: int = Field(default=1, ge=1)
    """Total marks a voter may distribute in this section (Hamburg: 5)."""

    max_per_target: int = Field(default=1, ge=1)
    """Kumulieren limit: marks a voter may pile on one target. 1 = no cumulation."""

    panachage: bool = False
    """Whether marks in this section may be split across parties."""

    decides_district: bool = False
    """Whether this section's counts decide the single-winner contest at its level."""

    @model_validator(mode="after")
    def _check_limits(self) -> BallotSection:
        if self.max_per_target > self.votes_per_voter:
            raise ValueError(
                f"section {self.name!r}: cannot pile {self.max_per_target} marks on one "
                f"target when a voter has only {self.votes_per_voter}"
            )
        if self.panachage and self.votes_per_voter == 1:
            raise ValueError(f"section {self.name!r}: one vote cannot be panaschiert")
        if self.decides_district and self.attaches_to is Attachment.PARTY:
            raise ValueError(f"section {self.name!r}: a district contest is won by a person")
        return self


class TallyKey(Model):
    """Addresses one counted quantity -- the four columns that identify a row.

    Exactly one of ``party`` / ``candidate`` is set. Kept as its own hashable type
    because :class:`~wahlwerk.events.wahlpruefung.TallyAmendment` addresses counts by
    key, and because it is the natural index into a :class:`VoteTally`.
    """

    unit: UnitId
    section: SectionName
    party: PartyId | None = None
    candidate: CandidateId | None = None

    @model_validator(mode="after")
    def _check_target(self) -> TallyKey:
        if (self.party is None) == (self.candidate is None):
            raise ValueError(
                "a count names either a party or a candidate, not both and not neither"
            )
        return self


class TallyRow(TallyKey):
    """One counted quantity: a key plus its count. One row of ``tally.csv``."""

    count: Count

    @property
    def key(self) -> TallyKey:
        return TallyKey(
            unit=self.unit,
            section=self.section,
            party=self.party,
            candidate=self.candidate,
        )


class TurnoutRow(Model):
    """Ballot papers per unit and section -- the denominators.

    A threshold is a share of *valid votes*, which is not recoverable from cumulated
    candidate counts, so it has to be carried separately rather than derived.
    """

    unit: UnitId
    section: SectionName
    valid: Count
    invalid: Count = 0
    eligible: Count | None = None
    """Wahlberechtigte."""

    cast: Count | None = None
    """Wähler. Only needed for turnout metrics, not for allocation."""


class VoteTally(Model):
    """Aggregated votes for one election: the sole numeric input to the pipeline."""

    rows: tuple[TallyRow, ...] = ()
    turnout: tuple[TurnoutRow, ...] = ()

    @model_validator(mode="after")
    def _check_unique_keys(self) -> VoteTally:
        seen: set[TallyKey] = set()
        for row in self.rows:
            if row.key in seen:
                raise ValueError(f"duplicate tally row: {row.key}")
            seen.add(row.key)
        return self

    @cached_property
    def index(self) -> dict[TallyKey, int]:
        return {row.key: row.count for row in self.rows}

    @cached_property
    def valid(self) -> dict[tuple[UnitId, SectionName], int]:
        return {(t.unit, t.section): t.valid for t in self.turnout}

    def get(self, key: TallyKey) -> int:
        return self.index.get(key, 0)

    def select(
        self,
        *,
        unit: UnitId | None = None,
        section: SectionName | None = None,
        party: PartyId | None = None,
        candidate: CandidateId | None = None,
    ) -> Iterator[TallyRow]:
        """Iterate the rows matching every constraint given."""
        for row in self.rows:
            if unit is not None and row.unit != unit:
                continue
            if section is not None and row.section != section:
                continue
            if party is not None and row.party != party:
                continue
            if candidate is not None and row.candidate != candidate:
                continue
            yield row

    def total(self, *, unit: UnitId | None = None, section: SectionName | None = None) -> int:
        return sum(row.count for row in self.select(unit=unit, section=section))


@runtime_checkable
class BallotStructure(Protocol):
    """The ballot schema of one law."""

    @property
    def sections(self) -> Sequence[BallotSection]:
        """All sections, in the order they appear on the paper."""
        ...

    def section(self, name: SectionName) -> BallotSection:
        """Look up one section. Raises :class:`KeyError` if unknown."""
        ...

    def validate_tally(self, tally: VoteTally, tiers: TierStructure) -> Sequence[str]:
        """Return human-readable complaints about a tally; empty means admissible.

        Checks that sections exist, that counts sit on units of the section's level,
        that the attachment matches (no candidate rows in a party-only section), and
        that per-voter and cumulation limits are not exceeded in aggregate.
        """
        ...
