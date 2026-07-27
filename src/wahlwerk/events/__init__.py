"""Events: the only things that produce new state."""

from __future__ import annotations

from wahlwerk.events.aufloesung import (
    Aufloesung,
    Division,
    Kanzlerwahl,
    Misstrauensvotum,
    Phase,
    Vertrauensfrage,
)
from wahlwerk.events.base import BodyState, Event, replay, trace
from wahlwerk.events.election import Election
from wahlwerk.events.nachruecken import (
    Abspaltung,
    Fraktionswechsel,
    Nachruecken,
    Vacancy,
    VacancyCause,
)
from wahlwerk.events.results import ElectionInput, ElectionResult
from wahlwerk.events.wahlpruefung import (
    Remedy,
    SeatChange,
    TallyAmendment,
    Wahlpruefung,
)

__all__ = [
    "Abspaltung",
    "Aufloesung",
    "BodyState",
    "Division",
    "Election",
    "ElectionInput",
    "ElectionResult",
    "Event",
    "Fraktionswechsel",
    "Kanzlerwahl",
    "Misstrauensvotum",
    "Nachruecken",
    "Phase",
    "Remedy",
    "SeatChange",
    "TallyAmendment",
    "Vacancy",
    "VacancyCause",
    "Vertrauensfrage",
    "Wahlpruefung",
    "replay",
    "trace",
]
