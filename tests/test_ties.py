"""A tie must survive as a tie until someone decides it."""

from __future__ import annotations

import pytest

from wahlwerk.ties import Deterministic, RecordedLot, RefuseToBreak, Tie, UnresolvedTie

TIE = Tie(contenders=frozenset({"spd", "cdu"}), seats=1, context="bund/last-seat")


def test_the_default_refuses_to_invent_an_answer() -> None:
    with pytest.raises(UnresolvedTie) as excinfo:
        RefuseToBreak().break_tie(TIE)
    assert excinfo.value.tie is TIE
    assert "drawing lots" in str(excinfo.value)


def test_a_recorded_lot_replays_the_draw_that_actually_happened() -> None:
    lot = RecordedLot(draws={"bund/last-seat": ("cdu",)})
    assert lot.break_tie(TIE) == ("cdu",)


def test_a_recorded_lot_refuses_a_tie_it_has_no_record_of() -> None:
    lot = RecordedLot(draws={"some/other/context": ("spd",)})
    with pytest.raises(UnresolvedTie):
        lot.break_tie(TIE)


def test_a_recorded_lot_may_delegate_unknown_ties() -> None:
    lot = RecordedLot(draws={}, fallback=Deterministic())
    assert lot.break_tie(TIE) == ("cdu",)


def test_the_sweep_breaker_is_stable_and_returns_exactly_the_contested_seats() -> None:
    assert Deterministic().break_tie(TIE) == ("cdu",)
    three = Tie(contenders=frozenset({"a", "b", "c"}), seats=2, context="x")
    assert Deterministic().break_tie(three) == ("a", "b")
