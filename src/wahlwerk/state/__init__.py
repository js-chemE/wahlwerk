"""Standing state: inert data that only events may replace."""

from __future__ import annotations

from wahlwerk.mandate import Mandate, MandateSource
from wahlwerk.state.chamber import Chamber, Fraktion, Term
from wahlwerk.state.government import (
    CoalitionAgreement,
    Government,
    InvestitureBasis,
    VoteStance,
)

__all__ = [
    "Chamber",
    "CoalitionAgreement",
    "Fraktion",
    "Government",
    "InvestitureBasis",
    "Mandate",
    "MandateSource",
    "Term",
    "VoteStance",
]
