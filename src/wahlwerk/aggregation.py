"""Slot 3 -- aggregation rule.

Which votes feed the proportional entitlement.

    Bund        Zweitstimmen only
    Bayern      Erststimmen *and* Zweitstimmen summed (Art. 42 LWG)
    open list   candidate votes roll up to the list

The rule turns a :class:`~wahlwerk.ballots.VoteTally` into
:class:`AggregatedVotes`: party totals per unit at every level, candidate totals per
unit, and the denominators a threshold is measured against. Everything downstream --
eligibility, apportionment, assignment -- reads this object and never the raw tally.

Rolling leaf counts up the tree is the aggregation rule's job, not the tier
structure's, because *which* sections roll up is exactly what varies between laws.
"""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction
from typing import Protocol, runtime_checkable

from wahlwerk.ballots import VoteTally
from wahlwerk.ids import CandidateId, LevelName, Nominations, PartyId, UnitId
from wahlwerk.model import Count, Model
from wahlwerk.tiers import TierStructure

__all__ = ["AggregatedVotes", "AggregationRule"]


class AggregatedVotes(Model):
    """Vote totals as the law counts them, at every unit of every level."""

    party: dict[UnitId, dict[PartyId, Count]] = {}
    """Votes counting towards proportional entitlement. Present for every unit at
    every level, so a national total is ``party[bund]`` and a Land total is
    ``party[land]`` without the caller having to sum."""

    candidate: dict[UnitId, dict[CandidateId, Count]] = {}
    """Personal votes, where the ballot has them. Feeds the ordering of open lists."""

    district: dict[UnitId, dict[CandidateId, Count]] = {}
    """Votes deciding the single-winner contest, per district unit. Distinct from
    ``candidate`` because Bayern counts the Erststimme towards *both* the district
    contest and the proportional entitlement, while federally it counts only towards
    the district."""

    valid: dict[UnitId, Count] = {}
    """Denominator for percentage thresholds, per unit."""

    def total(self, unit: UnitId) -> int:
        """Sum of party votes in one unit."""
        return sum(self.party.get(unit, {}).values())

    def share(self, unit: UnitId, party: PartyId) -> Fraction:
        """A party's exact share of the valid votes in one unit.

        Uses ``valid`` where it is known and falls back to the sum of party votes,
        because the two differ wherever a ballot allows cumulation.
        """
        denominator = self.valid.get(unit) or self.total(unit)
        if not denominator:
            return Fraction(0)
        return Fraction(self.party.get(unit, {}).get(party, 0), denominator)


@runtime_checkable
class AggregationRule(Protocol):
    """Turns a tally into the vote totals the rest of the pipeline works from."""

    @property
    def entitlement_sections(self) -> tuple[str, ...]:
        """Ballot sections feeding the proportional entitlement. Documentation for the
        law summary, and the one-line difference between Bund and Bayern."""
        ...

    def aggregate(
        self,
        tally: VoteTally,
        tiers: TierStructure,
        nominations: Nominations,
    ) -> AggregatedVotes: ...

    def party_votes(
        self, votes: AggregatedVotes, level: LevelName, tiers: TierStructure
    ) -> Mapping[UnitId, Mapping[PartyId, int]]:
        """Convenience view: party totals restricted to one level."""
        ...
