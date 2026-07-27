"""Identifiers and the nomination data every election runs on.

These types are deliberately law-agnostic. Nothing here knows what a Wahlkreis or a
Landesliste is -- it knows only that territory is made of *units*, that parties field
*candidacies* in those units, and that a candidacy is either for a single-winner
district contest or for a list.

Party attributes that laws care about (national minority status, for instance) are
carried as free-form ``tags`` rather than as named boolean fields, so that
:mod:`wahlwerk.eligibility` can express an exemption without this module having to
know which exemptions exist.

Identifier scheme
-----------------

Every stable key in wahlwerk is a lowercase ASCII dotted path, narrowest scope last::

    body        de.bund.bundestag      de.by.landtag      de.hh.buergerschaft
    law         de.bund.bwahlg.2023    de.bw.lwg.2022
    law variant de.bund.bwahlg.2023+apportionment
    unit        de.bund.land.01        de.bund.wk.001
    party       cdu   gruene   team-todenhoefer
    level       wahlkreis   land   bund
    section     erststimme   zweitstimme

Lowercase and ASCII because these keys appear in filenames, CSV cells, URLs and command
lines, and because a key that differs only in case or in an umlaut is a bug nobody
finds. That is the same split as the language policy: identifiers transliterate,
prose does not.

The convention is *enforced*, not merely documented -- each id type below is a
:class:`~typing.NewType` over a pattern-constrained string, so ``"de.bund.Bundestag"``
fails validation where it is first constructed. The ``NewType`` also keeps the types
distinct for mypy, so a :data:`PartyId` cannot be passed where a :data:`UnitId` belongs.

A ``BodyId`` names an institution; it is deliberately just a key. The institution
*model* -- name, jurisdiction, Bundesrat vote weight, election calendar -- arrives with
M6, when the Bundesrat needs the sixteen Länder as data rather than as strings.
"""

from __future__ import annotations

from enum import Enum
from functools import cached_property
from typing import Annotated, NewType

from pydantic import StringConstraints, model_validator

from wahlwerk.model import Model

__all__ = [
    "BodyId",
    "Candidacy",
    "CandidacyKind",
    "CandidateId",
    "DottedKey",
    "LawId",
    "LevelName",
    "Nominations",
    "Party",
    "PartyId",
    "Person",
    "SectionName",
    "Slug",
    "UnitId",
]

SLUG = r"[a-z0-9]+(?:[-_][a-z0-9]+)*"
"""One segment: lowercase ASCII, inner hyphens or underscores, no leading separator."""

Slug = Annotated[str, StringConstraints(pattern=rf"^{SLUG}$")]
"""A single-segment key: ``wahlkreis``, ``zweitstimme``, ``cdu-csu``."""

DottedKey = Annotated[str, StringConstraints(pattern=rf"^{SLUG}(?:\.{SLUG})*$")]
"""A dotted path, narrowest scope last: ``de.bund.wk.001``."""

LawId = Annotated[
    str, StringConstraints(pattern=rf"^{SLUG}(?:\.{SLUG})*(?:\+{SLUG}(?:\.{SLUG})*)*$")
]
"""A dotted path, optionally carrying ``+slot`` suffixes for counterfactual variants:
``de.bund.bwahlg.2023+apportionment``. See :meth:`~wahlwerk.law.ElectoralLaw.variant`."""

BodyId = NewType("BodyId", DottedKey)
"""Stable key of an institution, e.g. ``"de.bund.bundestag"``, ``"de.by.landtag"``.

Held by :class:`~wahlwerk.state.chamber.Term`,
:class:`~wahlwerk.state.chamber.Chamber`,
:class:`~wahlwerk.state.government.Government`,
:class:`~wahlwerk.events.base.BodyState` and :class:`~wahlwerk.law.ElectoralLaw`, which
is why it is defined once here rather than typed as ``str`` in five places."""

PartyId = NewType("PartyId", DottedKey)
"""Stable party key, e.g. ``"cdu"``. A Fraktionsgemeinschaft is *not* a party.
Dotted rather than flat so a Land-level registry can scope one: ``sh.ssw``."""

CandidateId = NewType("CandidateId", DottedKey)
"""Stable person key. Persistent across elections where the source data allows it."""

UnitId = NewType("UnitId", DottedKey)
"""Stable key of a territorial unit at any tier level, e.g. ``"de.bund.wk.001"``."""

LevelName = NewType("LevelName", Slug)
"""Name of a tier level, e.g. ``"wahlkreis"``, ``"land"``, ``"bund"``."""

SectionName = NewType("SectionName", Slug)
"""Name of a section of the ballot paper, e.g. ``"erststimme"``, ``"zweitstimme"``."""


class Party(Model):
    """A party or other grouping that can hold an entitlement to seats.

    ``tags`` carries law-relevant properties without hard-coding them here. The SSW
    would be tagged ``{"national_minority"}``; CSU and CDU are separate parties whose
    joint Fraktion is modelled in :class:`wahlwerk.state.chamber.Fraktion`.
    """

    id: PartyId
    name: str
    short_name: str = ""
    tags: frozenset[str] = frozenset()


class Person(Model):
    """A natural person who may hold a mandate."""

    id: CandidateId
    name: str


class CandidacyKind(Enum):
    """How a candidacy can win a seat."""

    DISTRICT = "district"
    """Single-winner contest in one unit (Wahlkreis-, Stimmkreis-, Direktmandat)."""

    LIST = "list"
    """A position on a party list attached to one unit (Landesliste, Bezirksliste)."""


class Candidacy(Model):
    """One candidate standing in one unit.

    The same person routinely holds two candidacies (district plus list); mandate
    assignment is responsible for never seating them twice.
    """

    candidate: CandidateId
    unit: UnitId
    kind: CandidacyKind
    party: PartyId | None = None
    """``None`` for an independent (Einzelbewerber)."""

    list_position: int | None = None
    """1-based position as filed. ``None`` for district candidacies and for pure
    open-list systems where the filed order carries no weight."""

    @model_validator(mode="after")
    def _check_list_position(self) -> Candidacy:
        if self.list_position is not None:
            if self.list_position < 1:
                raise ValueError("list_position is 1-based")
            if self.kind is CandidacyKind.DISTRICT:
                raise ValueError("a district candidacy has no list position")
        return self


class Nominations(Model):
    """The complete set of candidacies admitted to one election."""

    candidacies: tuple[Candidacy, ...] = ()
    persons: tuple[Person, ...] = ()

    @model_validator(mode="after")
    def _check_unique(self) -> Nominations:
        seen: set[tuple[str, str, CandidacyKind]] = set()
        for c in self.candidacies:
            key = (c.candidate, c.unit, c.kind)
            if key in seen:
                raise ValueError(f"duplicate candidacy: {c.candidate} in {c.unit}")
            seen.add(key)
        return self

    @cached_property
    def person(self) -> dict[CandidateId, Person]:
        return {p.id: p for p in self.persons}

    @cached_property
    def by_unit(self) -> dict[UnitId, tuple[Candidacy, ...]]:
        index: dict[UnitId, list[Candidacy]] = {}
        for c in self.candidacies:
            index.setdefault(c.unit, []).append(c)
        return {unit: tuple(cs) for unit, cs in index.items()}

    @cached_property
    def by_party(self) -> dict[PartyId | None, tuple[Candidacy, ...]]:
        index: dict[PartyId | None, list[Candidacy]] = {}
        for c in self.candidacies:
            index.setdefault(c.party, []).append(c)
        return {party: tuple(cs) for party, cs in index.items()}

    @cached_property
    def by_candidate(self) -> dict[CandidateId, tuple[Candidacy, ...]]:
        index: dict[CandidateId, list[Candidacy]] = {}
        for c in self.candidacies:
            index.setdefault(c.candidate, []).append(c)
        return {who: tuple(cs) for who, cs in index.items()}

    def of_unit(self, unit: UnitId, kind: CandidacyKind | None = None) -> tuple[Candidacy, ...]:
        found = self.by_unit.get(unit, ())
        return found if kind is None else tuple(c for c in found if c.kind is kind)

    def of_party(
        self, party: PartyId, kind: CandidacyKind | None = None
    ) -> tuple[Candidacy, ...]:
        found = self.by_party.get(party, ())
        return found if kind is None else tuple(c for c in found if c.kind is kind)

    def list_of(self, party: PartyId, unit: UnitId) -> tuple[Candidacy, ...]:
        """A party's list in one unit, in the order filed."""
        return tuple(
            sorted(
                (
                    c
                    for c in self.by_unit.get(unit, ())
                    if c.party == party and c.kind is CandidacyKind.LIST
                ),
                key=lambda c: (c.list_position is None, c.list_position or 0),
            )
        )
