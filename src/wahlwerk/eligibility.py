"""Slot 4 -- eligibility filter.

Threshold, the tier at which it is computed, and exemptions.

    Bund      5 % of Zweitstimmen nationally, *plus* the Grundmandatsklausel
              (>= 3 constituency wins), *plus* the national-minority exemption (SSW)
    Länder   usually 5 % statewide
    Kommunal  usually no threshold at all -- municipal thresholds have repeatedly
              been struck down by constitutional courts

The interface is shaped to the federal wording literally: a party is

    excluded unless (threshold met) OR (any exemption satisfied)

so :class:`EligibilityVerdict` records, per party, both the arithmetic and which
exemption -- if any -- carried it. That record is what the counterfactual harness
reports on when the Grundmandatsklausel is switched off.

Note the input coupling: the Grundmandatsklausel needs district wins, so the pipeline
resolves districts *before* eligibility. That ordering is fixed in
:mod:`wahlwerk.events.election`.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cached_property
from typing import Protocol, runtime_checkable

from pydantic import model_validator

from wahlwerk.aggregation import AggregatedVotes
from wahlwerk.assignment import DistrictOutcome
from wahlwerk.ids import Party, PartyId
from wahlwerk.model import Model, Share
from wahlwerk.tiers import TierStructure

__all__ = ["EligibilityFilter", "EligibilityVerdict", "PartyStanding"]


class PartyStanding(Model):
    """Why one party is in or out."""

    party: PartyId
    admitted: bool
    share: Share | None = None
    """Share of valid votes at the level the threshold is measured on. Exact."""

    threshold_met: bool = False
    exemption: str | None = None
    """Name of the exemption that carried the party, e.g. ``"grundmandatsklausel"``
    or ``"nationale_minderheit"``. ``None`` if it cleared the threshold outright."""

    reason: str = ""

    @model_validator(mode="after")
    def _check_consistent(self) -> PartyStanding:
        if self.admitted and not (self.threshold_met or self.exemption):
            raise ValueError(
                f"{self.party} is admitted without meeting the threshold and without "
                f"an exemption -- record which one carried it"
            )
        if self.exemption and not self.admitted:
            raise ValueError(f"{self.party} satisfies {self.exemption!r} yet is excluded")
        return self


class EligibilityVerdict(Model):
    """Which parties take part in the apportionment."""

    standings: tuple[PartyStanding, ...] = ()

    @model_validator(mode="after")
    def _check_unique(self) -> EligibilityVerdict:
        seen = {s.party for s in self.standings}
        if len(seen) != len(self.standings):
            raise ValueError("a party has more than one standing")
        return self

    @cached_property
    def by_party(self) -> dict[PartyId, PartyStanding]:
        return {s.party: s for s in self.standings}

    @cached_property
    def admitted(self) -> frozenset[PartyId]:
        return frozenset(s.party for s in self.standings if s.admitted)

    @cached_property
    def excluded(self) -> frozenset[PartyId]:
        return frozenset(s.party for s in self.standings if not s.admitted)

    @cached_property
    def carried_by_exemption(self) -> dict[PartyId, str]:
        """Parties that would have been excluded on the threshold alone.

        The single most interesting output of a counterfactual sweep over slot 4.
        """
        return {
            s.party: s.exemption
            for s in self.standings
            if s.admitted and s.exemption and not s.threshold_met
        }


@runtime_checkable
class EligibilityFilter(Protocol):
    """Decides which parties are admitted to the proportional allocation."""

    def apply(
        self,
        votes: AggregatedVotes,
        tiers: TierStructure,
        districts: DistrictOutcome,
        parties: Mapping[PartyId, Party],
    ) -> EligibilityVerdict: ...
