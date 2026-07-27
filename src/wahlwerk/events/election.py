"""The Election event: derives a fresh chamber from a law and a set of votes.

The pipeline is fixed and runs in this order:

    1. ballot.validate_tally         is this tally admissible under this law?
    2. aggregation.aggregate         which votes count, rolled up to every level
    3. assignment.resolve_districts  who won the single-winner contests
    4. eligibility.apply             which parties take part  (needs 3, for Grundmandate)
    5. apportionment.apportion       proportional entitlement (needs 4)
    6. assignment.assign             who occupies the seats   (needs 3 and 5)

Steps 3 and 6 are the same slot, split because eligibility sits between them. That is
the only ordering constraint the six-slot decomposition imposes.

:class:`~wahlwerk.events.results.ElectionResult` keeps the computed chamber, the
official one where it is known, and the complete inputs. The distinction between the
result *as declared* and *as computed* is what makes a golden test meaningful and a
Wahlprüfung possible.
"""

from __future__ import annotations

from datetime import date

from pydantic import model_validator

from wahlwerk.events.base import BodyState
from wahlwerk.events.results import ElectionInput, ElectionResult
from wahlwerk.law import ElectoralLaw
from wahlwerk.model import SlotModel
from wahlwerk.state.chamber import Chamber

__all__ = ["Election", "ElectionInput", "ElectionResult"]


class Election(SlotModel):
    """Derives a fresh chamber. M0: interface only."""

    at: date
    law: ElectoralLaw
    inputs: ElectionInput
    declared: Chamber | None = None
    term_number: int | None = None
    label: str = ""

    @model_validator(mode="after")
    def _check_law_applies(self) -> Election:
        if not self.law.applies_on(self.at):
            raise ValueError(
                f"{self.law.id} was not in force on {self.at.isoformat()} "
                f"(valid {self.law.valid_from} .. {self.law.valid_until or 'open'})"
            )
        return self

    def derive(self) -> ElectionResult:
        """Run the six-step pipeline above and return the result.

        Implemented in M1 against BWahlG-2023.
        """
        raise NotImplementedError("election pipeline lands in M1")

    def apply(self, state: BodyState) -> BodyState:
        result = self.derive()
        return state.logging(
            self.label or f"Election under {self.law.id}",
            at=self.at,
            chamber=result.computed,
            government=None,
            origin=result,
        )
