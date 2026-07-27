"""What an election consumed and what it produced.

Split out from :mod:`wahlwerk.events.election` so that
:class:`~wahlwerk.events.base.BodyState` can hold an :class:`ElectionResult` without
the two modules importing each other. Nothing here imports
:class:`~wahlwerk.law.ElectoralLaw`: a result records the law's ``id``, not the object,
so a result stays serialisable.
"""

from __future__ import annotations

from datetime import date

from wahlwerk.aggregation import AggregatedVotes
from wahlwerk.apportionment.tiered import Entitlement
from wahlwerk.assignment import AssignmentResult
from wahlwerk.ballots import VoteTally
from wahlwerk.eligibility import EligibilityVerdict
from wahlwerk.ids import LawId, Nominations, Party
from wahlwerk.model import Model, SlotModel
from wahlwerk.state.chamber import Chamber
from wahlwerk.ties import Tie, TieBreaker

__all__ = ["ElectionInput", "ElectionResult"]


class ElectionInput(SlotModel):
    """Everything an election consumes besides the law itself.

    Held whole on the result so that amending one number and re-running is a
    :meth:`~pydantic.BaseModel.model_copy` away. This is what makes a Wahlprüfung a
    re-derivation rather than surgery on a finished chamber.
    """

    tally: VoteTally
    nominations: Nominations = Nominations()
    parties: tuple[Party, ...] = ()
    lots: TieBreaker | None = None
    """Losentscheide as actually drawn, for a faithful replay."""

    source: str = ""
    """Provenance of the vote data -- required for attribution under dl-de/by-2-0."""

    @property
    def party_index(self) -> dict[str, Party]:
        return {p.id: p for p in self.parties}


class ElectionResult(Model):
    """Everything one run of the pipeline produced."""

    law_id: LawId
    day: date
    inputs: ElectionInput
    votes: AggregatedVotes = AggregatedVotes()
    eligibility: EligibilityVerdict = EligibilityVerdict()
    entitlement: Entitlement = Entitlement()
    assignment: AssignmentResult = AssignmentResult()
    computed: Chamber
    declared: Chamber | None = None
    """The officially declared composition, where it is on record. A golden test
    asserts ``computed == declared``; a Wahlprüfung is the case where they part."""

    ties: tuple[Tie, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def matches_declaration(self) -> bool | None:
        """``None`` where no declaration is on record."""
        if self.declared is None:
            return None
        return self.computed.seats_by_party == self.declared.seats_by_party
