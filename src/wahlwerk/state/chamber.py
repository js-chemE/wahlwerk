"""Standing composition of a body. Inert data -- only events produce new state."""

from __future__ import annotations

from datetime import date
from functools import cached_property
from pathlib import Path

from pydantic import model_validator

from wahlwerk.ids import BodyId, CandidateId, PartyId, Slug
from wahlwerk.mandate import Mandate, MandateSource
from wahlwerk.model import Model

__all__ = ["Chamber", "Fraktion", "Mandate", "MandateSource", "Term"]


class Term(Model):
    """A legislative period.

    ``actual_end`` differs from ``scheduled_end`` after an Auflösung under Art. 68 GG.
    """

    body: BodyId
    """The institution this term is a Wahlperiode of, e.g. ``de.bund.bundestag``."""

    start: date | None = None
    """First day of the term. Federally that is the constitutive session, which is when
    the Wahlperiode begins (Art. 39 (1) GG) -- *not* the election day. ``None`` where only
    the election is on record: a published seat distribution does not say when the new
    chamber first met, and defaulting one date to the other would make them silently
    interchangeable."""

    elected_on: date | None = None
    """Election day. Distinct from ``start``: the outgoing Bundestag's term runs on until
    the new one convenes."""

    scheduled_end: date | None = None
    actual_end: date | None = None
    number: int | None = None
    """Wahlperiode, where the body numbers them."""

    @model_validator(mode="after")
    def _check_order(self) -> Term:
        if (
            self.start is not None
            and self.elected_on is not None
            and self.start < self.elected_on
        ):
            raise ValueError(
                f"{self.body}: term starts {self.start}, before the election on "
                f"{self.elected_on}"
            )
        if self.start is None:
            return self
        ends = (("scheduled_end", self.scheduled_end), ("actual_end", self.actual_end))
        for label, end in ends:
            if end is not None and end < self.start:
                raise ValueError(f"{self.body}: {label} {end} precedes start {self.start}")
        return self

    @property
    def ended(self) -> bool:
        return self.actual_end is not None

    @property
    def ended_early(self) -> bool:
        return (
            self.actual_end is not None
            and self.scheduled_end is not None
            and self.actual_end < self.scheduled_end
        )


class Fraktion(Model):
    """A grouping over mandates, with its own membership rules.

    Distinct from a party: CDU and CSU are two parties in one Fraktionsgemeinschaft,
    which is why ``parties`` is a set. ``recognised`` records whether the grouping
    meets the body's own threshold -- 5 % of members under Sec. 10 (1) GO-BT -- below
    which it is a Gruppe with fewer rights rather than a Fraktion.
    """

    id: Slug
    name: str
    parties: frozenset[PartyId] = frozenset()
    members: frozenset[CandidateId] = frozenset()
    declared_size: int | None = None
    """Membership as published, for a chamber recorded only in aggregate. Where the
    members are known this must agree with them."""

    recognised: bool = True
    since: date | None = None

    @model_validator(mode="after")
    def _check_size(self) -> Fraktion:
        if (
            self.declared_size is not None
            and self.members
            and self.declared_size != len(self.members)
        ):
            raise ValueError(
                f"Fraktion {self.id}: {len(self.members)} members recorded but "
                f"{self.declared_size} declared"
            )
        return self

    @property
    def size(self) -> int:
        return len(self.members) if self.members else (self.declared_size or 0)

    @property
    def is_gemeinschaft(self) -> bool:
        """More than one party under one roof."""
        return len(self.parties) > 1


class Chamber(Model):
    """The set of mandates constituting a body at a point in time."""

    body: BodyId
    term: Term
    mandates: tuple[Mandate, ...] = ()
    fraktionen: tuple[Fraktion, ...] = ()

    @model_validator(mode="after")
    def _check_seats_unique(self) -> Chamber:
        seats = [m.seat for m in self.mandates]
        if len(set(seats)) != len(seats):
            raise ValueError(f"{self.body}: two mandates on one seat")
        people = [m.person for m in self.mandates if m.person is not None]
        if len(set(people)) != len(people):
            raise ValueError(f"{self.body}: a person holds two mandates")
        return self

    @classmethod
    def from_archive(cls, election_id: str, root: Path | None = None) -> Chamber:
        """The chamber an election produced, read from the wahlwerk-data archive.

        >>> Chamber.from_archive("de.bund.2025").size      # doctest: +SKIP
        630

        One mandate per seat, carrying its party and the unit whose list it came from.
        Nothing is derived -- this is the *declared* result, which is what makes it usable
        as the target a derivation must reproduce.

        Raises :class:`~wahlwerk.io.archive.ArchiveNotFound` if no archive is resolvable;
        see :func:`~wahlwerk.io.archive.find_archive` for where it looks. Imported inside
        the method so that ``state`` never depends on ``io`` at module level.
        """
        from wahlwerk.io.archive import load_chamber

        return load_chamber(election_id, root)

    @property
    def size(self) -> int:
        return len(self.mandates)

    @cached_property
    def seats_by_party(self) -> dict[PartyId | None, int]:
        counts: dict[PartyId | None, int] = {}
        for mandate in self.mandates:
            counts[mandate.party] = counts.get(mandate.party, 0) + 1
        return counts

    @cached_property
    def by_seat(self) -> dict[str, Mandate]:
        return {m.seat: m for m in self.mandates}

    @cached_property
    def by_person(self) -> dict[CandidateId, Mandate]:
        return {m.person: m for m in self.mandates if m.person is not None}

    @property
    def vacant_seats(self) -> tuple[str, ...]:
        return tuple(m.seat for m in self.mandates if m.vacant)

    def holder_of(self, seat: str) -> Mandate | None:
        return self.by_seat.get(seat)

    def replacing(self, seat: str, mandate: Mandate) -> Chamber:
        """Copy with the mandate on ``seat`` replaced -- the Nachrücken primitive."""
        if seat not in self.by_seat:
            raise KeyError(f"{self.body} has no seat {seat!r}")
        return Chamber(
            body=self.body,
            term=self.term,
            mandates=tuple(mandate if m.seat == seat else m for m in self.mandates),
            fraktionen=self.fraktionen,
        )
