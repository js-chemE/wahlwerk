"""Government: derived from a chamber via an investiture rule, never from an election.

Keeping this separate from :class:`~wahlwerk.state.chamber.Chamber` is what lets
Art. 63 and Art. 67 GG be events that change the government without touching a single
mandate.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import model_validator

from wahlwerk.ids import BodyId, CandidateId, PartyId
from wahlwerk.model import Model

__all__ = ["CoalitionAgreement", "Government", "InvestitureBasis", "VoteStance"]


class InvestitureBasis(Enum):
    """How the head of government took office."""

    ELECTED_ABSOLUTE = "elected_absolute"
    """Art. 63 (2) GG -- Kanzlermehrheit."""

    ELECTED_PLURALITY = "elected_plurality"
    """Art. 63 (4) GG -- elected without an absolute majority."""

    CONSTRUCTIVE_NO_CONFIDENCE = "constructive_no_confidence"
    """Art. 67 GG."""

    CARETAKER = "caretaker"
    """Geschäftsführend, Art. 69 (3) GG."""


class VoteStance(Enum):
    """How a government casts a bloc vote in a derived body.

    ``ABSTAIN`` is not a shade of ``NO`` in the Bundesrat -- an absolute majority of 35
    of 69 is required, so an abstention counts against a proposal exactly as a no vote
    does. Coalition agreements at Land level routinely *require* abstention where
    partners disagree, which makes this the highest-leverage detail in the whole model.
    """

    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"

    @property
    def counts_towards_majority(self) -> bool:
        """Only YES counts. This property exists so the rule is stated once."""
        return self is VoteStance.YES


class CoalitionAgreement(Model):
    """The clause that decides a Land's Bundesrat behaviour under disagreement."""

    parties: frozenset[PartyId] = frozenset()
    abstain_on_disagreement: bool = True
    signed: date | None = None
    stances: dict[str, VoteStance] = {}
    """Explicit per-subject stances, where they are known."""


class Government(Model):
    """The executive resting on one chamber."""

    body: BodyId
    head: CandidateId | None = None
    head_name: str = ""
    parties: frozenset[PartyId] = frozenset()
    basis: InvestitureBasis = InvestitureBasis.ELECTED_ABSOLUTE
    since: date | None = None
    until: date | None = None
    coalition: CoalitionAgreement | None = None

    @model_validator(mode="after")
    def _check_dates(self) -> Government:
        if self.since and self.until and self.until < self.since:
            raise ValueError(f"{self.body}: government ends before it starts")
        return self
