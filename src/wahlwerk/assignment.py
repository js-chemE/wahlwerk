"""Slot 6 -- mandate assignment.

Who actually occupies the seats, and how constituency winners are reconciled with the
proportional entitlement. This is the slot the 2023 federal reform changed, and where
the Länder differ most sharply:

    Bund since 2023   Zweitstimmendeckung: a constituency winner enters only if the
                      party's second votes cover the seat; the excess winners with the
                      weakest results do not enter. Total capped at 630, no Überhang,
                      no Ausgleich.
    BW from 2026      constituency winners always enter; shortfalls are filled from
                      Landeslisten; Überhang and Ausgleich retained, so the Landtag
                      grows past its minimum of 120.

Two consequences for the interface, both load-bearing:

1.  ``assign`` receives the entitlement and returns the *final* seat totals. Ausgleich
    changes house size after apportionment, so assignment cannot be a pure lookup into
    a fixed allocation. Conversely Zweitstimmendeckung drops winners the entitlement
    does not cover. Both are the same call with different bodies.
2.  District resolution lives here, not in aggregation, because it is a question about
    who occupies a seat. It is exposed separately so that
    :mod:`wahlwerk.eligibility` can consult it for the Grundmandatsklausel before the
    apportionment runs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import cached_property
from typing import Protocol, runtime_checkable

from wahlwerk.aggregation import AggregatedVotes
from wahlwerk.ids import CandidateId, LevelName, Nominations, PartyId, UnitId
from wahlwerk.mandate import Mandate, MandateSource
from wahlwerk.model import Count, Model, Seats
from wahlwerk.tiers import TierStructure
from wahlwerk.ties import Tie, TieBreaker

__all__ = [
    "AssignmentResult",
    "AssignmentRule",
    "DistrictOutcome",
    "DistrictWin",
    "MandateSource",
]


class DistrictWin(Model):
    """Outcome of one single-winner contest."""

    unit: UnitId
    winner: CandidateId | None = None
    party: PartyId | None = None
    votes: Count = 0
    seated: bool = True
    """False where the law lets a winner go unseated -- Zweitstimmendeckung. Set by
    :meth:`AssignmentRule.assign`, not by district resolution."""


class DistrictOutcome(Model):
    """All single-winner contests of one election."""

    wins: tuple[DistrictWin, ...] = ()
    ties: tuple[Tie, ...] = ()

    @cached_property
    def by_unit(self) -> dict[UnitId, DistrictWin]:
        return {win.unit: win for win in self.wins}

    @cached_property
    def count_by_party(self) -> dict[PartyId, int]:
        """Wins per party -- the input to the Grundmandatsklausel.

        Counts contests won, not seats taken: a winner left unseated under
        Zweitstimmendeckung still won the Wahlkreis, and Sec. 4 (2) BWahlG counts
        exactly that.
        """
        counts: dict[PartyId, int] = {}
        for win in self.wins:
            if win.party is not None:
                counts[win.party] = counts.get(win.party, 0) + 1
        return counts


class AssignmentResult(Model):
    """Seats as finally occupied."""

    mandates: tuple[Mandate, ...] = ()
    seats: dict[UnitId, dict[PartyId, Seats]] = {}
    """Final seat counts per unit per party. May differ from the entitlement handed in
    -- Ausgleich adds seats, Zweitstimmendeckung removes constituency winners."""

    districts: DistrictOutcome = DistrictOutcome()
    """District outcomes with ``seated`` decided."""

    ties: tuple[Tie, ...] = ()
    unfilled: dict[UnitId, dict[PartyId, Seats]] = {}
    """Seats a party is entitled to but cannot fill: its list is exhausted."""

    notes: tuple[str, ...] = ()
    """Diagnostics -- how many Überhang seats, which winners were dropped, why."""

    @property
    def size(self) -> int:
        """House size actually produced."""
        return len(self.mandates)


@runtime_checkable
class AssignmentRule(Protocol):
    """Fills the seats."""

    def resolve_districts(
        self,
        votes: AggregatedVotes,
        tiers: TierStructure,
        nominations: Nominations,
        breaker: TieBreaker | None = None,
    ) -> DistrictOutcome:
        """Decide every single-winner contest. Runs before eligibility."""
        ...

    def assign(
        self,
        entitlement: Mapping[UnitId, Mapping[PartyId, int]],
        votes: AggregatedVotes,
        tiers: TierStructure,
        nominations: Nominations,
        districts: DistrictOutcome,
        breaker: TieBreaker | None = None,
    ) -> AssignmentResult:
        """Reconcile district winners with the entitlement and seat the people."""
        ...

    def list_order(
        self,
        unit: UnitId,
        party: PartyId,
        votes: AggregatedVotes,
        nominations: Nominations,
    ) -> Sequence[CandidateId]:
        """Order in which a list is drawn down.

        Closed lists return the filed order; open lists return the order by personal
        votes. Isolating this is what keeps Hamburg from touching the rest of the slot.
        """
        ...

    def successor(
        self,
        vacated: Mandate,
        seated: Sequence[CandidateId],
        votes: AggregatedVotes,
        nominations: Nominations,
    ) -> CandidateId | None:
        """Next eligible candidate for a vacated seat. Drives Nachrücken."""
        ...

    @property
    def allocation_level(self) -> LevelName:
        """Level whose units the returned ``seats`` mapping is keyed on."""
        ...
