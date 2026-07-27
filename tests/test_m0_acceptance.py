"""M0 acceptance: the Bayern and Hamburg quirks fit the six protocols unchanged.

The milestone criterion is that the two hardest divergences can each be *described* as
a slot implementation without touching a protocol:

    Bayern    slot 1  three levels, allocation per Regierungsbezirk, no state pot
              slot 3  Erst- and Zweitstimmen summed into the entitlement
    Hamburg   slot 2  five votes per section, cumulation to five, panachage,
                      votes attaching to people rather than parties
              slot 6  list order by personal vote instead of filed order

The stubs below are not implementations of those laws -- they carry no arithmetic.
They exist so that mypy checks the signatures structurally and pytest checks that a
law composed of them is a well-formed :class:`ElectoralLaw`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

import pytest

from wahlwerk import (
    AggregatedVotes,
    AggregationRule,
    AssignmentResult,
    AssignmentRule,
    Attachment,
    BallotSection,
    BallotStructure,
    DistrictOutcome,
    ElectoralLaw,
    EligibilityFilter,
    EligibilityVerdict,
    Entitlement,
    LawRegistry,
    LevelName,
    Nominations,
    Party,
    PartyId,
    SeatConstraints,
    SeatTargets,
    SectionName,
    TieredApportionment,
    TierStructure,
    Unit,
    UnitId,
    VoteTally,
)
from wahlwerk.apportionment.base import Key
from wahlwerk.ids import BodyId, CandidateId
from wahlwerk.mandate import Mandate
from wahlwerk.ties import TieBreaker

pytestmark = pytest.mark.m0


# --------------------------------------------------------------------------- stubs


class StubTiers:
    """Slot 1. Configured, not subclassed -- Bund, Bayern and Hamburg differ only in
    the level names, the district level and which levels allocate."""

    def __init__(
        self,
        levels: Sequence[str],
        *,
        district_level: str | None,
        allocation_levels: Sequence[str],
    ) -> None:
        self._levels = tuple(LevelName(x) for x in levels)
        self._district = LevelName(district_level) if district_level else None
        self._alloc = tuple(LevelName(x) for x in allocation_levels)

    @property
    def levels(self) -> Sequence[LevelName]:
        return self._levels

    @property
    def district_level(self) -> LevelName | None:
        return self._district

    @property
    def allocation_levels(self) -> Sequence[LevelName]:
        return self._alloc

    def units(self, level: LevelName) -> Sequence[Unit]:
        return ()

    def unit(self, unit_id: UnitId) -> Unit:
        raise KeyError(unit_id)

    def parent(self, unit_id: UnitId) -> UnitId | None:
        return None

    def children(self, unit_id: UnitId) -> Sequence[UnitId]:
        return ()

    def ancestor_at(self, unit_id: UnitId, level: LevelName) -> UnitId | None:
        return None

    def descendants_at(self, unit_id: UnitId, level: LevelName) -> Sequence[UnitId]:
        return ()


class StubBallot:
    """Slot 2."""

    def __init__(self, sections: Sequence[BallotSection]) -> None:
        self._sections = tuple(sections)

    @property
    def sections(self) -> Sequence[BallotSection]:
        return self._sections

    def section(self, name: SectionName) -> BallotSection:
        for section in self._sections:
            if section.name == name:
                return section
        raise KeyError(name)

    def validate_tally(self, tally: VoteTally, tiers: TierStructure) -> Sequence[str]:
        return ()


class StubAggregation:
    """Slot 3. The Bund/Bayern difference is one tuple."""

    def __init__(self, sections: Sequence[str]) -> None:
        self._sections = tuple(sections)

    @property
    def entitlement_sections(self) -> tuple[str, ...]:
        return self._sections

    def aggregate(
        self, tally: VoteTally, tiers: TierStructure, nominations: Nominations
    ) -> AggregatedVotes:
        return AggregatedVotes(party={}, candidate={})

    def party_votes(
        self, votes: AggregatedVotes, level: LevelName, tiers: TierStructure
    ) -> Mapping[UnitId, Mapping[PartyId, int]]:
        return votes.party


class StubEligibility:
    """Slot 4."""

    def apply(
        self,
        votes: AggregatedVotes,
        tiers: TierStructure,
        districts: DistrictOutcome,
        parties: Mapping[PartyId, Party],
    ) -> EligibilityVerdict:
        return EligibilityVerdict()


class StubApportionment:
    """Slot 5."""

    def __init__(self, levels: Sequence[str]) -> None:
        self._levels = tuple(levels)

    @property
    def levels(self) -> Sequence[str]:
        return self._levels

    def apportion(
        self,
        votes: Mapping[str, Mapping[Key, int]],
        targets: SeatTargets,
        constraints: Mapping[str, SeatConstraints] | None = None,
    ) -> Entitlement:
        return Entitlement(by_level={level: {} for level in self._levels})


class StubAssignment:
    """Slot 6. ``by_personal_vote`` is the whole Hamburg difference."""

    def __init__(self, level: str, *, by_personal_vote: bool = False) -> None:
        self._level = LevelName(level)
        self.by_personal_vote = by_personal_vote

    @property
    def allocation_level(self) -> LevelName:
        return self._level

    def resolve_districts(
        self,
        votes: AggregatedVotes,
        tiers: TierStructure,
        nominations: Nominations,
        breaker: TieBreaker | None = None,
    ) -> DistrictOutcome:
        return DistrictOutcome()

    def assign(
        self,
        entitlement: Mapping[UnitId, Mapping[PartyId, int]],
        votes: AggregatedVotes,
        tiers: TierStructure,
        nominations: Nominations,
        districts: DistrictOutcome,
        breaker: TieBreaker | None = None,
    ) -> AssignmentResult:
        return AssignmentResult(districts=districts)

    def list_order(
        self,
        unit: UnitId,
        party: PartyId,
        votes: AggregatedVotes,
        nominations: Nominations,
    ) -> Sequence[CandidateId]:
        return ()

    def successor(
        self,
        vacated: Mandate,
        seated: Sequence[CandidateId],
        votes: AggregatedVotes,
        nominations: Nominations,
    ) -> CandidateId | None:
        return None


# ------------------------------------------------------------ static conformance
# mypy is doing the real work here: passing a stub to a parameter annotated with the
# protocol fails the type check if a signature drifts.


def _takes_tiers(x: TierStructure) -> None: ...
def _takes_ballot(x: BallotStructure) -> None: ...
def _takes_aggregation(x: AggregationRule) -> None: ...
def _takes_eligibility(x: EligibilityFilter) -> None: ...
def _takes_apportionment(x: TieredApportionment) -> None: ...
def _takes_assignment(x: AssignmentRule) -> None: ...


# ----------------------------------------------------------------------- fixtures


def bayern_law() -> ElectoralLaw:
    """Bayern: 91 Stimmkreise -> 7 Wahlkreise -> Land, Erst- und Zweitstimmen summed,
    seats apportioned per Regierungsbezirk with no state-level pot."""
    return ElectoralLaw(
        id="de.by.lwg.sketch",
        body=BodyId("de.by.landtag"),
        valid_from=date(2013, 1, 1),
        valid_until=None,
        tiers=StubTiers(
            ["stimmkreis", "wahlkreis", "land"],
            district_level="stimmkreis",
            allocation_levels=["wahlkreis"],
        ),
        ballot=StubBallot(
            [
                BallotSection(
                    name=SectionName("erststimme"),
                    level=LevelName("stimmkreis"),
                    attaches_to=Attachment.CANDIDATE,
                    decides_district=True,
                ),
                BallotSection(
                    name=SectionName("zweitstimme"),
                    level=LevelName("wahlkreis"),
                    attaches_to=Attachment.EITHER,
                ),
            ]
        ),
        aggregation=StubAggregation(["erststimme", "zweitstimme"]),
        eligibility=StubEligibility(),
        apportionment=StubApportionment(["wahlkreis"]),
        assignment=StubAssignment("wahlkreis", by_personal_vote=True),
        seats=SeatTargets(total=180),
    )


def hamburg_law() -> ElectoralLaw:
    """Hamburg: five Wahlkreis votes and five Landeslisten votes, cumulable up to five
    on one target and freely panachiert, attaching to people."""
    return ElectoralLaw(
        id="de.hh.buergwahlg.sketch",
        body=BodyId("de.hh.buergerschaft"),
        valid_from=date(2013, 1, 1),
        valid_until=None,
        tiers=StubTiers(
            ["wahlkreis", "land"],
            district_level=None,
            allocation_levels=["land", "wahlkreis"],
        ),
        ballot=StubBallot(
            [
                BallotSection(
                    name=SectionName("wahlkreisstimmen"),
                    level=LevelName("wahlkreis"),
                    attaches_to=Attachment.CANDIDATE,
                    votes_per_voter=5,
                    max_per_target=5,
                    panachage=True,
                ),
                BallotSection(
                    name=SectionName("landesstimmen"),
                    level=LevelName("land"),
                    attaches_to=Attachment.EITHER,
                    votes_per_voter=5,
                    max_per_target=5,
                    panachage=True,
                ),
            ]
        ),
        aggregation=StubAggregation(["wahlkreisstimmen", "landesstimmen"]),
        eligibility=StubEligibility(),
        apportionment=StubApportionment(["land", "wahlkreis"]),
        assignment=StubAssignment("land", by_personal_vote=True),
        seats=SeatTargets(minimum=121),
    )


# -------------------------------------------------------------------------- tests


@pytest.mark.parametrize("law", [bayern_law(), hamburg_law()], ids=["bayern", "hamburg"])
def test_quirks_compose_without_touching_the_protocols(law: ElectoralLaw) -> None:
    _takes_tiers(law.tiers)
    _takes_ballot(law.ballot)
    _takes_aggregation(law.aggregation)
    _takes_eligibility(law.eligibility)
    _takes_apportionment(law.apportionment)
    _takes_assignment(law.assignment)

    assert isinstance(law.tiers, TierStructure)
    assert isinstance(law.ballot, BallotStructure)
    assert isinstance(law.aggregation, AggregationRule)
    assert isinstance(law.eligibility, EligibilityFilter)
    assert isinstance(law.apportionment, TieredApportionment)
    assert isinstance(law.assignment, AssignmentRule)


def test_bayern_sums_both_votes_and_allocates_per_bezirk() -> None:
    law = bayern_law()
    assert law.aggregation.entitlement_sections == ("erststimme", "zweitstimme")
    assert law.tiers.district_level == "stimmkreis"
    assert list(law.tiers.allocation_levels) == ["wahlkreis"], "no state-level pot"


def test_hamburg_ballot_carries_cumulation_and_panachage() -> None:
    law = hamburg_law()
    section = law.ballot.section(SectionName("landesstimmen"))
    assert section.votes_per_voter == 5
    assert section.max_per_target == 5
    assert section.panachage
    assert section.attaches_to is Attachment.EITHER
    assert law.tiers.district_level is None, "no single-winner contest in Hamburg"


def test_a_reform_is_the_law_with_one_slot_replaced() -> None:
    base = bayern_law()
    reform = base.variant(apportionment=StubApportionment(["land"]))

    assert reform.derived_from == base.id
    assert reform.id == f"{base.id}+apportionment"
    assert list(reform.apportionment.levels) == ["land"]
    assert reform.tiers is base.tiers, "untouched slots are shared, not copied"
    assert list(base.apportionment.levels) == ["wahlkreis"], "base is unchanged"


def test_variant_rejects_a_field_that_is_not_a_slot() -> None:
    with pytest.raises(ValueError, match="not a replaceable law field"):
        bayern_law().variant(threshold=0.03)


def test_registry_resolves_by_date_and_refuses_overlaps() -> None:
    old = bayern_law().model_copy(
        update={
            "id": "de.by.lwg.2003",
            "valid_from": date(2003, 1, 1),
            "valid_until": date(2012, 12, 31),
        }
    )
    new = bayern_law()
    registry = LawRegistry().with_laws([old, new])

    assert registry.resolve(BodyId("de.by.landtag"), date(2008, 9, 28)).id == "de.by.lwg.2003"
    assert registry.resolve(BodyId("de.by.landtag"), date(2023, 10, 8)).id == "de.by.lwg.sketch"

    with pytest.raises(LookupError, match="no law"):
        registry.resolve(BodyId("de.by.landtag"), date(1990, 1, 1))
    with pytest.raises(LookupError, match="overlapping"):
        LawRegistry().with_laws([new, new.model_copy(update={"id": "dup"})]).resolve(
            BodyId("de.by.landtag"), date(2023, 10, 8)
        )
