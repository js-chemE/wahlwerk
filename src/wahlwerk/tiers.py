"""Slot 1 -- tier structure.

How territory maps to allocation units, and how the units nest.

    Bund: 299 Wahlkreise -> 16 Länder -> Bund
    BW: 70 Wahlkreise -> Land
    Bayern: 91 Stimmkreise -> 7 Wahlkreise (Regierungsbezirke) -> Land
    Kommunal: one unit, or N Wahlbezirke

The structure is a forest of :class:`Unit` nodes arranged in named *levels*. Two
distinctions matter downstream and are therefore explicit rather than inferred:

``district_level``
    the level whose units run single-winner contests (Wahlkreis federally,
    Stimmkreis in Bayern, ``None`` for a pure list system).

``allocation_levels``
    the levels at which proportional entitlement is computed, ordered from the
    binding one downwards. Federally that is ``("bund", "land")``: the national
    result binds, Land lists divide it. In Bayern it is ``("wahlkreis",)`` alone --
    each Regierungsbezirk apportions independently and there is no state-level pot.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import model_validator

from wahlwerk.ids import LevelName, UnitId
from wahlwerk.model import Model, Seats

__all__ = ["TierStructure", "Unit"]


class Unit(Model):
    """One territorial unit at one level."""

    id: UnitId
    name: str
    level: LevelName
    parent: UnitId | None = None
    seats: Seats | None = None
    """Seats fixed to this unit by law, where the law fixes them (BW: 1 per Wahlkreis;
    Bayern: a fixed contingent per Regierungsbezirk). ``None`` where the unit's share
    falls out of the apportionment instead."""

    population: int | None = None
    """Only where the law apportions seats to units by population."""

    tags: frozenset[str] = frozenset()

    @model_validator(mode="after")
    def _check_not_own_parent(self) -> Unit:
        if self.parent == self.id:
            raise ValueError(f"unit {self.id} cannot be its own parent")
        return self


@runtime_checkable
class TierStructure(Protocol):
    """Read-only view of the unit hierarchy for one law."""

    @property
    def levels(self) -> Sequence[LevelName]:
        """All levels, ordered from the finest (leaves) to the coarsest (root)."""
        ...

    @property
    def district_level(self) -> LevelName | None:
        """Level running single-winner contests, or ``None`` if the law has none."""
        ...

    @property
    def allocation_levels(self) -> Sequence[LevelName]:
        """Levels at which proportional entitlement is computed, binding tier first."""
        ...

    def units(self, level: LevelName) -> Sequence[Unit]:
        """All units at ``level``."""
        ...

    def unit(self, unit_id: UnitId) -> Unit:
        """Look up one unit. Raises :class:`KeyError` if unknown."""
        ...

    def parent(self, unit_id: UnitId) -> UnitId | None:
        """Immediate parent, or ``None`` at the root level."""
        ...

    def children(self, unit_id: UnitId) -> Sequence[UnitId]:
        """Immediate children, empty at the leaf level."""
        ...

    def ancestor_at(self, unit_id: UnitId, level: LevelName) -> UnitId | None:
        """The ancestor of ``unit_id`` at ``level`` (or itself, if already there)."""
        ...

    def descendants_at(self, unit_id: UnitId, level: LevelName) -> Sequence[UnitId]:
        """All units at ``level`` beneath ``unit_id``."""
        ...
