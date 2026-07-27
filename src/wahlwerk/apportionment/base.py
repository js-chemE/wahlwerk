"""Apportionment methods: vote counts and a seat total in, an allocation out.

Nothing in this subpackage may know anything about Germany. It takes opaque keys and
integer votes. If a Land quirk appears here, the abstraction is broken.

Exact arithmetic is mandatory. Divisor methods compare :class:`fractions.Fraction` or
scaled integers, never floats: float rounding both hides real ties and manufactures
fake ones, and the symptom is a seat count off by one that costs days to find. This is
also why :data:`~wahlwerk.model.Share` and the divisor below are ``Fraction`` -- pydantic
validates and serialises them exactly (``"12345/7"``), with no decimal round trip.
"""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction
from typing import Protocol, runtime_checkable

from pydantic import Field, model_validator

from wahlwerk.model import Count, Model, Seats
from wahlwerk.ties import Tie

__all__ = ["Allocation", "ApportionmentMethod", "Key", "SeatConstraints"]

Key = str
"""Opaque allocation key -- a party id here, a list id one tier down."""


class SeatConstraints(Model):
    """Per-key bounds an allocation must respect.

    ``minimums`` carries guaranteed seats (a party's constituency wins, where the law
    guarantees them). ``maximums`` carries caps (a list shorter than its entitlement).
    Both are generic -- the *reason* for the bound stays in the calling slot.
    """

    minimums: dict[Key, Seats] = {}
    maximums: dict[Key, Seats] = {}

    @model_validator(mode="after")
    def _check_satisfiable(self) -> SeatConstraints:
        for key, low in self.minimums.items():
            high = self.maximums.get(key)
            if high is not None and high < low:
                raise ValueError(f"{key}: minimum {low} exceeds maximum {high}")
        return self


class Allocation(Model):
    """Seats assigned, plus the evidence needed to check the working.

    ``ties`` non-empty means the allocation is *provisional*: some keys are exactly
    level for the last seat and the law prescribes lots. ``seats`` then reflects the
    breaker that was supplied, or the call raised.
    """

    seats: dict[Key, Seats] = {}
    divisor: Fraction | None = Field(default=None, gt=0)
    """Divisor that produced the result, for divisor methods. Exact, and the single
    most useful number when a golden test is one seat off."""

    quota: Fraction | None = Field(default=None, gt=0)
    """Quota used, for quota methods."""

    ties: tuple[Tie, ...] = ()
    remainders: dict[Key, Fraction] = {}
    """Fractional remainders, for quota methods."""

    @property
    def total(self) -> int:
        return sum(self.seats.values())

    @property
    def provisional(self) -> bool:
        """True while a tie in this allocation is still undecided."""
        return bool(self.ties)


@runtime_checkable
class ApportionmentMethod(Protocol):
    """One method of turning votes into seats."""

    @property
    def name(self) -> str: ...

    def allocate(
        self,
        votes: Mapping[Key, Count],
        seats: int,
        constraints: SeatConstraints | None = None,
    ) -> Allocation:
        """Distribute exactly ``seats`` among ``votes`` keys."""
        ...

    def divisor_for(self, votes: Mapping[Key, Count], seats: int) -> Fraction | None:
        """Divisor yielding ``seats``, or ``None`` for non-divisor methods.

        Split out because multi-tier linkage searches for a divisor across tiers
        rather than allocating tier by tier.
        """
        ...
