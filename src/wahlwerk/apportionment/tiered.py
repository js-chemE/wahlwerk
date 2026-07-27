"""Multi-tier apportionment: which pots are filled, in what order, bound by what.

Still no German content. The vocabulary is: an *upper* allocation over keys in one
pot, then a *lower* allocation of each key's result across its sub-units, optionally
*linked* so that the upper result binds the lower totals.

The federal two-tier scheme (nationally among parties, then across Land lists within
each party) is a composition of :class:`~wahlwerk.apportionment.base.ApportionmentMethod`
under this rule, not a method of its own. Bayern's per-Regierungsbezirk allocation is
the same rule with a single, unlinked tier.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from pydantic import model_validator

from wahlwerk.apportionment.base import Allocation, Key, SeatConstraints
from wahlwerk.model import Count, Model, Seats
from wahlwerk.ties import Tie

__all__ = ["Entitlement", "SeatTargets", "TieredApportionment"]


class SeatTargets(Model):
    """How many seats each allocation unit is playing for.

    ``fixed`` pins a unit's contingent (Bayern's per-Bezirk seats). ``total`` pins the
    house size where the law fixes that instead. ``cap`` bounds a house that is
    otherwise allowed to grow; ``minimum`` floors one that is (BW: 120).
    """

    total: Seats | None = None
    fixed: dict[str, Seats] = {}
    cap: Seats | None = None
    minimum: Seats | None = None

    @model_validator(mode="after")
    def _check_bounds(self) -> SeatTargets:
        if self.cap is not None and self.minimum is not None and self.cap < self.minimum:
            raise ValueError(f"cap {self.cap} is below minimum {self.minimum}")
        for label, value in (("total", self.total), ("minimum", self.minimum)):
            if value is not None and self.cap is not None and value > self.cap:
                raise ValueError(f"{label} {value} exceeds cap {self.cap}")
        return self


class Entitlement(Model):
    """Proportional entitlement before anyone is seated.

    Keyed level -> unit -> key -> seats. Keeping the upper tier visible is what lets
    assignment tell a Land shortfall from a national one.
    """

    by_level: dict[str, dict[str, dict[Key, Seats]]] = {}
    ties: tuple[Tie, ...] = ()
    allocations: dict[str, Allocation] = {}
    """Raw allocation objects by unit, kept for divisors and audit trails."""

    def at(self, level: str) -> dict[str, dict[Key, Seats]]:
        return self.by_level[level]

    def total(self, level: str) -> int:
        return sum(
            seats for unit in self.by_level.get(level, {}).values() for seats in unit.values()
        )

    @property
    def provisional(self) -> bool:
        return bool(self.ties)


@runtime_checkable
class TieredApportionment(Protocol):
    """Resolves the tiers in the order the law prescribes."""

    @property
    def levels(self) -> Sequence[str]:
        """Allocation levels this rule fills, binding tier first."""
        ...

    def apportion(
        self,
        votes: Mapping[str, Mapping[Key, Count]],
        targets: SeatTargets,
        constraints: Mapping[str, SeatConstraints] | None = None,
    ) -> Entitlement:
        """Compute the entitlement.

        ``votes`` is unit -> key -> votes for every unit of every level this rule
        touches; ``constraints`` is keyed the same way.
        """
        ...
