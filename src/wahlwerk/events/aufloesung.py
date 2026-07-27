"""Term and government events: the ones that change state without an election.

    Auflösung        Art. 68 GG -- a failed Vertrauensfrage lets the President
                      dissolve; the term ends early and a scheduled election follows
                      within sixty days (Art. 39 (1) GG).
    Kanzlerwahl       Art. 63 GG -- investiture, in up to three phases with different
                      majority requirements.
    Misstrauensvotum  Art. 67 GG -- constructive: the chamber is unchanged, the
                      government is replaced only if a successor wins a majority.

All three change ``government`` or ``term`` while leaving every mandate in place.
That is the point of keeping the two apart in :mod:`wahlwerk.state`.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from wahlwerk.events.base import BodyState
from wahlwerk.ids import CandidateId, PartyId
from wahlwerk.model import Count, Model

__all__ = ["Aufloesung", "Kanzlerwahl", "Misstrauensvotum", "Phase", "Vertrauensfrage"]


class Phase(Enum):
    """The three phases of Art. 63 GG, which differ in required majority."""

    PROPOSED = "proposed"
    """Art. 63 (1)-(2): President proposes, absolute majority required."""

    CHAMBER_INITIATIVE = "chamber_initiative"
    """Art. 63 (3): fourteen days, absolute majority required."""

    PLURALITY = "plurality"
    """Art. 63 (4): plurality suffices; the President may then dissolve instead."""


class Division(Model):
    """A recorded division. Abstentions are kept apart from noes deliberately.

    Where the Kanzlermehrheit is required the test is a majority of *members*, so an
    abstention counts against the motion exactly as a no does -- the same asymmetry as
    :class:`~wahlwerk.state.government.VoteStance` in the Bundesrat.
    """

    yes: Count = 0
    no: Count = 0
    abstain: Count = 0
    invalid: Count = 0

    @property
    def cast(self) -> int:
        return self.yes + self.no + self.abstain + self.invalid

    def carried_by_members(self, chamber_size: int) -> bool:
        """Absolute majority of members -- Art. 63 (2), 67 (1), 68 (1) GG."""
        return self.yes > chamber_size // 2

    @property
    def carried_by_plurality(self) -> bool:
        """Art. 63 (4) GG, first sentence."""
        return self.yes > self.no


class Vertrauensfrage(Model):
    """Art. 68 GG. Failure is the precondition for :class:`Aufloesung`."""

    at: date
    division: Division = Division()
    label: str = ""

    def apply(self, state: BodyState) -> BodyState:
        raise NotImplementedError("Vertrauensfrage lands after M1")


class Aufloesung(Model):
    """Ends the term early and schedules the next election."""

    at: date
    election_due_by: date | None = None
    """Art. 39 (1) GG: within sixty days."""

    label: str = ""

    def apply(self, state: BodyState) -> BodyState:
        raise NotImplementedError("Auflösung lands after M1")


class Kanzlerwahl(Model):
    """Art. 63 GG investiture. Changes the government, never the chamber."""

    at: date
    candidate: CandidateId
    candidate_name: str = ""
    phase: Phase = Phase.PROPOSED
    division: Division = Division()
    coalition: frozenset[PartyId] = frozenset()
    label: str = ""

    def apply(self, state: BodyState) -> BodyState:
        raise NotImplementedError("Kanzlerwahl lands after M1")


class Misstrauensvotum(Model):
    """Art. 67 GG. Constructive: without a successor majority nothing happens."""

    at: date
    successor: CandidateId
    successor_name: str = ""
    division: Division = Division()
    label: str = ""

    def apply(self, state: BodyState) -> BodyState:
        raise NotImplementedError("Misstrauensvotum lands after M1")
