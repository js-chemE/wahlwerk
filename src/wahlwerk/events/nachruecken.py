"""Nachrücken: a mandate is vacated and the next eligible candidate fills it.

Who is next is a slot-6 question -- :meth:`AssignmentRule.successor` -- because a
closed list draws down in the filed order while an open list draws down by personal
votes, and the same event must work for both. The event itself only decides *that* a
seat is refilled, and from which list.

A seat may also stay empty: if the list is exhausted the seat lapses (federally,
Sec. 48 (1) BWahlG), and if the vacating member held a Direktmandat under a law without
list backing there is a by-election instead.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from wahlwerk.events.base import BodyState
from wahlwerk.ids import CandidateId
from wahlwerk.model import Model

__all__ = [
    "Abspaltung",
    "Fraktionswechsel",
    "Nachruecken",
    "Vacancy",
    "VacancyCause",
]


class VacancyCause(Enum):
    DEATH = "death"
    RESIGNATION = "resignation"
    LOSS_OF_ELIGIBILITY = "loss_of_eligibility"
    APPOINTMENT_ELSEWHERE = "appointment_elsewhere"
    """Took an office incompatible with the mandate."""

    ANNULMENT = "annulment"
    """Seat struck by a Wahlprüfung."""


class Vacancy(Model):
    """A seat falls empty. Does not fill it -- that is :class:`Nachruecken`."""

    at: date
    seat: str
    person: CandidateId
    cause: VacancyCause
    label: str = ""

    def apply(self, state: BodyState) -> BodyState:
        raise NotImplementedError("vacancy handling lands with M1 state plumbing")


class Nachruecken(Model):
    """Fills a vacated seat from the successor list."""

    at: date
    seat: str
    successor: CandidateId | None = None
    """Explicit successor, for replaying a recorded case. ``None`` asks the law's
    assignment rule to determine it."""

    lapses: bool = False
    """True where the list is exhausted and the seat stays empty."""

    label: str = ""

    def apply(self, state: BodyState) -> BodyState:
        raise NotImplementedError("Nachrücken lands after M1")


# Regrouping events: membership changes, mandates do not.


class Fraktionswechsel(Model):
    """A member changes Fraktion. The mandate is untouched -- it is held personally."""

    at: date
    person: CandidateId
    to_fraktion: str | None = None
    """``None`` for fraktionslos."""

    label: str = ""

    def apply(self, state: BodyState) -> BodyState:
        raise NotImplementedError("Fraktionswechsel lands after M1")


class Abspaltung(Model):
    """A group leaves to form a new Fraktion or Gruppe (cf. BSW from Die Linke).

    ``recognised`` is decided against the body's own threshold -- 5 % of members under
    Sec. 10 (1) GO-BT -- and below it the new grouping is a Gruppe, not a Fraktion.
    """

    at: date
    members: frozenset[CandidateId]
    new_fraktion_id: str
    new_fraktion_name: str
    from_fraktion: str | None = None
    label: str = ""

    def apply(self, state: BodyState) -> BodyState:
        raise NotImplementedError("Abspaltung lands after M1")
