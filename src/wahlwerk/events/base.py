"""Events are the only things that produce new state.

    State --(Event)--> State

Elections are one event type among several, and designing as though they were the only
one is the single most likely architectural mistake here. A Fraktionswechsel regroups
without touching mandates; a Kanzlerwahl changes the government without touching the
chamber; a Wahlprüfung amends the *inputs* and re-derives the election.

:class:`BodyState` therefore keeps ``origin``: the election result the current chamber
was computed from, with its inputs attached. Without it a Wahlprüfung cannot be
anything but surgery on a finished chamber, which is exactly the failure mode this
design exists to avoid.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from typing import Protocol, runtime_checkable

from wahlwerk.events.results import ElectionResult
from wahlwerk.ids import BodyId
from wahlwerk.model import Model
from wahlwerk.state.chamber import Chamber
from wahlwerk.state.government import Government

__all__ = ["BodyState", "Event", "replay", "trace"]


class BodyState(Model):
    """Everything true about one body at one moment."""

    body: BodyId
    at: date
    chamber: Chamber | None = None
    government: Government | None = None
    origin: ElectionResult | None = None
    """The election this chamber was derived from, inputs included, so that the result
    can be re-derived when the inputs are amended."""

    history: tuple[str, ...] = ()
    """Human-readable log of the events applied, in order."""

    def logging(self, note: str, **changes: object) -> BodyState:
        """Successor state with ``note`` appended to the history.

        Every event body ends in a call to this, so that no transition can quietly
        leave the history untouched.
        """
        return self.model_copy(update={**changes, "history": (*self.history, note)})


@runtime_checkable
class Event(Protocol):
    """A dated transition between two states."""

    @property
    def at(self) -> date: ...

    @property
    def label(self) -> str:
        """Short description, appended to :attr:`BodyState.history`."""
        ...

    def apply(self, state: BodyState) -> BodyState:
        """Return the successor state. Must not mutate ``state``."""
        ...


def replay(initial: BodyState, events: Iterable[Event]) -> BodyState:
    """Fold events over a state in chronological order.

    Events are sorted by date; ties keep the order given, since two events on one day
    (a resignation and the Nachrücken filling it) are ordered by the record, not the
    clock.
    """
    state = initial
    for event in sorted(events, key=lambda e: e.at):
        state = event.apply(state)
    return state


def trace(initial: BodyState, events: Sequence[Event]) -> list[BodyState]:
    """Like :func:`replay`, but keeps every intermediate state."""
    states = [initial]
    for event in sorted(events, key=lambda e: e.at):
        states.append(event.apply(states[-1]))
    return states
