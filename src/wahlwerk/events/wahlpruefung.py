"""Wahlprüfung: vote data is amended after the fact and the election is re-derived.

This event is the acceptance test for the whole design. It requires three things the
architecture must already provide, and which are painful to retrofit:

  * amended *inputs* rather than a patched result -- :class:`TallyAmendment` produces
    a new :class:`~wahlwerk.events.results.ElectionInput`;
  * a re-derivable election -- :attr:`BodyState.origin` keeps the inputs, so
    re-running is replaying the same pipeline over a changed tally;
  * a distinction between declared and computed -- the amended run is compared against
    the original declaration to determine which seats actually move.

Procedure: objection to the Bundestag under the Wahlprüfungsgesetz, then Beschwerde to
the BVerfG under Art. 41 (2) GG. Only the outcome is modelled -- the court is never an
agent.

Do not implement first. Do not design so that it becomes surgery later.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from enum import Enum

from wahlwerk.ballots import TallyRow, VoteTally
from wahlwerk.events.base import BodyState
from wahlwerk.events.results import ElectionInput, ElectionResult
from wahlwerk.ids import UnitId
from wahlwerk.model import Model

__all__ = ["Remedy", "SeatChange", "TallyAmendment", "Wahlpruefung"]


class Remedy(Enum):
    """What the reviewing body ordered."""

    NONE = "none"
    """Objection rejected; the declared result stands."""

    RECOUNT = "recount"
    """Counts corrected; the election is re-derived on the amended tally."""

    PARTIAL_RERUN = "partial_rerun"
    """Some units vote again; their counts are replaced wholesale (Berlin 2021/2024)."""

    FULL_RERUN = "full_rerun"
    """The election is annulled and repeated -- a new Election event, not this one."""


class TallyAmendment(Model):
    """A correction to the vote data of an election already declared.

    Rows, not a mapping, so an amendment is itself a small CSV -- reviewable next to
    the tally it corrects.
    """

    corrections: tuple[TallyRow, ...] = ()
    """Absolute counts overwriting existing rows, matched on the four key columns."""

    rerun_units: frozenset[UnitId] = frozenset()
    """Units voting again: all their existing rows are discarded before applying
    ``corrections``."""

    note: str = ""

    def apply_to(self, tally: VoteTally) -> VoteTally:
        """Return the amended tally. Implemented alongside the Wahlprüfung fixture."""
        raise NotImplementedError("tally amendment lands with the Berlin 2021 fixture")


class SeatChange(Model):
    """One seat that moved between the declared and the re-derived result."""

    seat: str
    unit: UnitId
    left: str | None = None
    entered: str | None = None
    reason: str = ""


class Wahlpruefung(Model):
    """Re-derives an election from amended inputs."""

    at: date
    remedy: Remedy
    amendment: TallyAmendment = TallyAmendment()
    docket: str = ""
    """Case reference, e.g. ``2 BvC 4/23``."""

    label: str = ""

    def amended_input(self, original: ElectionInput) -> ElectionInput:
        return original.model_copy(update={"tally": self.amendment.apply_to(original.tally)})

    def rederive(self, origin: ElectionResult) -> ElectionResult:
        """Re-run the original election's law over the amended inputs."""
        raise NotImplementedError("re-derivation lands with the Berlin 2021 fixture")

    def changes(self, origin: ElectionResult, amended: ElectionResult) -> Sequence[SeatChange]:
        """Seats that moved. This, not the new chamber, is what the report is about."""
        raise NotImplementedError("re-derivation lands with the Berlin 2021 fixture")

    def apply(self, state: BodyState) -> BodyState:
        if state.origin is None:
            raise ValueError("cannot re-derive: state carries no election of origin")
        if self.remedy is Remedy.NONE:
            return state.logging(
                self.label or f"Wahlprüfung {self.docket}: objection rejected",
                at=self.at,
            )
        amended = self.rederive(state.origin)
        return state.logging(
            self.label or f"Wahlprüfung {self.docket}: {self.remedy.value}",
            at=self.at,
            chamber=amended.computed,
            origin=amended,
        )
