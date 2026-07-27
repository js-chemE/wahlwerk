"""The law object: six slots plus validity dates.

Comparing BWahlG-2021 against BWahlG-2023 on identical votes is the core use case, so
versioning is not optional. A reform proposal is a law object with one field replaced
-- :meth:`ElectoralLaw.variant` is the whole counterfactual mechanism.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from pydantic import model_validator

from wahlwerk.aggregation import AggregationRule
from wahlwerk.apportionment.tiered import SeatTargets, TieredApportionment
from wahlwerk.assignment import AssignmentRule
from wahlwerk.ballots import BallotStructure
from wahlwerk.eligibility import EligibilityFilter
from wahlwerk.ids import BodyId, LawId
from wahlwerk.model import Model, SlotModel
from wahlwerk.tiers import TierStructure

__all__ = ["ElectoralLaw", "LawRegistry"]

SLOTS = ("tiers", "ballot", "aggregation", "eligibility", "apportionment", "assignment")
"""The six. Everything else on a law is metadata or configuration."""

_ALSO_REPLACEABLE = frozenset({"seats", "citation", "notes", "body"})


class ElectoralLaw(SlotModel):
    """One electoral law, valid over one period.

    ``id`` is a dotted key: ``de.bund.bwahlg.2023``, ``de.bw.lwg.2022``. A
    counterfactual variant derived through :meth:`variant` appends a suffix, so results
    stay traceable to the law that produced them.

    The six slot fields are :class:`typing.Protocol` types. Because they are
    ``runtime_checkable``, pydantic rejects an object that is missing a required
    method at construction time rather than three stages into a pipeline.
    """

    id: LawId
    body: BodyId
    """Body the law elects, e.g. ``de.bund.bundestag``."""

    valid_from: date
    valid_until: date | None = None

    tiers: TierStructure
    ballot: BallotStructure
    aggregation: AggregationRule
    eligibility: EligibilityFilter
    apportionment: TieredApportionment
    assignment: AssignmentRule

    seats: SeatTargets = SeatTargets()
    """House size as the law fixes it: 630 capped federally, 120 as a BW minimum."""

    citation: str = ""
    notes: str = ""
    derived_from: str | None = None
    """``id`` of the law this was derived from, if it is a counterfactual variant."""

    @model_validator(mode="after")
    def _check_validity_window(self) -> ElectoralLaw:
        if self.valid_until is not None and self.valid_until < self.valid_from:
            raise ValueError(
                f"{self.id}: valid_until {self.valid_until} precedes "
                f"valid_from {self.valid_from}"
            )
        return self

    def applies_on(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_until is None or day <= self.valid_until)

    def variant(self, *, id: str | None = None, **changes: Any) -> ElectoralLaw:
        """Return a copy with one or more slots replaced.

        >>> bwahlg_2023.variant(apportionment=dhondt_rule)     # doctest: +SKIP

        Any field may be replaced, but replacing one of the six slots is the intended
        use and the reason the decomposition exists. The copy is re-validated, so a
        variant cannot smuggle in an object that is not a slot implementation.
        """
        unknown = set(changes) - set(SLOTS) - _ALSO_REPLACEABLE
        if unknown:
            raise ValueError(f"not a replaceable law field: {sorted(unknown)}")
        data = {name: getattr(self, name) for name in type(self).model_fields}
        data.update(changes)
        data["id"] = id if id is not None else f"{self.id}+{'+'.join(sorted(changes))}"
        data["derived_from"] = self.id
        return ElectoralLaw.model_validate(data)

    def slot_summary(self) -> dict[str, str]:
        """One line per slot -- what this law actually is, at a glance."""
        return {name: type(getattr(self, name)).__name__ for name in SLOTS}


class LawRegistry(Model):
    """Laws for one or more bodies, resolvable by date."""

    laws: tuple[ElectoralLaw, ...] = ()

    def for_body(self, body: BodyId) -> tuple[ElectoralLaw, ...]:
        return tuple(law for law in self.laws if law.body == body)

    def resolve(self, body: BodyId, day: date) -> ElectoralLaw:
        """The law in force for ``body`` on ``day``.

        Raises :class:`LookupError` if none or more than one applies -- overlapping
        validity is a data error, not something to resolve by ordering.
        """
        matches = [law for law in self.for_body(body) if law.applies_on(day)]
        if not matches:
            raise LookupError(f"no law for {body} on {day.isoformat()}")
        if len(matches) > 1:
            raise LookupError(
                f"overlapping laws for {body} on {day.isoformat()}: "
                f"{sorted(law.id for law in matches)}"
            )
        return matches[0]

    def with_laws(self, laws: Iterable[ElectoralLaw]) -> LawRegistry:
        return LawRegistry(laws=self.laws + tuple(laws))
