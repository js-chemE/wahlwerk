"""A seat and how it was won.

Lives at the top level rather than in :mod:`wahlwerk.state` because both slot 6
(:mod:`wahlwerk.assignment`, which produces mandates) and the chamber (which holds
them) need it, and neither should have to import the other.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import Field, model_validator

from wahlwerk.ids import CandidateId, LevelName, PartyId, UnitId
from wahlwerk.model import Model

__all__ = ["Mandate", "MandateSource"]


class MandateSource(Enum):
    """How a mandate was won -- recorded on every seat."""

    DISTRICT = "district"
    """Direktmandat: won the single-winner contest and was seated."""

    LIST = "list"
    """Taken from a list in the order filed."""

    PERSONAL_VOTE = "personal_vote"
    """Taken from a list reordered by personal votes (open list, Kumulieren)."""

    UEBERHANG = "ueberhang"
    """Seat in excess of the party's proportional entitlement."""

    AUSGLEICH = "ausgleich"
    """Seat added to other parties to restore proportionality after Überhang."""

    UNRECORDED = "unrecorded"
    """Provenance not in the source. Legitimate for a chamber known only from a
    published seat distribution; never acceptable in a golden test, which asserts a
    result the engine derived and therefore knows the provenance of."""


class Mandate(Model):
    """One seat, and whoever holds it.

    ``person``, ``unit`` and ``level`` are optional because a seat can be real while
    those facts are not on record: a chamber reconstructed from a published seat
    distribution knows the party and nothing else, and a seat between a Vacancy and the
    Nachrücken that fills it has no holder at all.
    """

    seat: str
    """Stable seat key, so that Nachrücken can be traced to the seat it refilled."""

    person: CandidateId | None = None
    party: PartyId | None = None
    source: MandateSource = MandateSource.UNRECORDED
    unit: UnitId | None = None
    """District won, or the unit whose list the seat came from."""

    level: LevelName | None = None
    """Tier level the seat was allocated in."""

    list_position: int | None = Field(default=None, ge=1)
    since: date | None = None
    until: date | None = None
    predecessor: CandidateId | None = None
    """Set when this mandate came about through Nachrücken."""

    @model_validator(mode="after")
    def _check_dates(self) -> Mandate:
        if self.since and self.until and self.until < self.since:
            raise ValueError(f"seat {self.seat}: ends before it starts")
        return self

    @property
    def vacant(self) -> bool:
        return self.person is None
