"""Ties are a result, not an error.

When two parties are exactly level for the last seat, the law does not say "sort by
name" -- it says draw lots (Losentscheid, e.g. Sec. 6 (5) BWahlG). The engine must
therefore be able to *report* a tie rather than silently resolving it through Python's
stable sort order.

Every stage that could tie returns its result plus a tuple of :class:`Tie` records.
A :class:`TieBreaker` turns a tie into a decision; the default breaker refuses to,
which is what you want in a golden test. Historical replays supply
:class:`RecordedLot` with the lot as actually drawn.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import Field, model_validator

from wahlwerk.model import Model, SlotModel

__all__ = [
    "Deterministic",
    "RecordedLot",
    "RefuseToBreak",
    "Tie",
    "TieBreaker",
    "UnresolvedTie",
]


class Tie(Model):
    """Contenders that are exactly level for fewer seats than they have claimants.

    ``contenders`` are opaque keys -- party ids in an apportionment, candidate ids in
    a district contest. ``context`` names where the tie arose, for reporting.
    """

    contenders: frozenset[str] = Field(min_length=2)
    seats: int = Field(ge=1)
    """How many of the tied claims can actually be satisfied. Always < len(contenders)."""

    context: str = ""

    @model_validator(mode="after")
    def _check_contested(self) -> Tie:
        if self.seats >= len(self.contenders):
            raise ValueError(
                f"{len(self.contenders)} contenders for {self.seats} seats is not a tie"
            )
        return self


class UnresolvedTie(Exception):
    """Raised when a definite result is demanded but a tie has not been broken."""

    def __init__(self, tie: Tie) -> None:
        super().__init__(
            f"tie between {sorted(tie.contenders)} for {tie.seats} seat(s)"
            + (f" in {tie.context}" if tie.context else "")
            + "; the law prescribes drawing lots -- supply a TieBreaker"
        )
        self.tie = tie


@runtime_checkable
class TieBreaker(Protocol):
    """Decides which of the tied contenders take the contested seats."""

    def break_tie(self, tie: Tie) -> tuple[str, ...]:
        """Return exactly ``tie.seats`` winners drawn from ``tie.contenders``."""
        ...


class RefuseToBreak(Model):
    """Default breaker: surfaces the tie instead of inventing an answer."""

    def break_tie(self, tie: Tie) -> tuple[str, ...]:
        raise UnresolvedTie(tie)


class RecordedLot(SlotModel):
    """Replays a lot that was actually drawn, keyed by tie context.

    Used in golden tests so that a historically drawn Losentscheid reproduces.
    """

    draws: dict[str, tuple[str, ...]] = {}
    fallback: TieBreaker | None = None

    def break_tie(self, tie: Tie) -> tuple[str, ...]:
        recorded = self.draws.get(tie.context)
        if recorded is None:
            if self.fallback is not None:
                return self.fallback.break_tie(tie)
            raise UnresolvedTie(tie)
        if len(recorded) != tie.seats:
            raise ValueError(
                f"recorded lot for {tie.context!r} names {len(recorded)} winners "
                f"but {tie.seats} seat(s) are contested"
            )
        unknown = set(recorded) - tie.contenders
        if unknown:
            raise ValueError(f"recorded lot names non-contenders: {sorted(unknown)}")
        return recorded


class Deterministic(Model):
    """Breaks ties by sorted key order.

    Legally wrong, but necessary for parameter sweeps where thousands of variants must
    each yield one number. Never use it in a golden test.
    """

    def break_tie(self, tie: Tie) -> tuple[str, ...]:
        return tuple(sorted(tie.contenders))[: tie.seats]
