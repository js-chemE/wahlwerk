"""wahlwerk -- German electoral and parliamentary systems as rules-as-code.

A deterministic engine parameterised by an electoral law, so that small changes to the
law can be evaluated against real historical votes.

Every law in scope decomposes into six orthogonal slots. That decomposition *is* the
modularity of the package:

    1  tiers         how territory maps to allocation units, and how they nest
    2  ballots       how many votes a voter casts and what they attach to
    3  aggregation   which votes feed the proportional entitlement
    4  eligibility   threshold, the tier it is computed at, and exemptions
    5  apportionment divisor and quota methods, and the order tiers resolve in
    6  assignment    who occupies the seats, and how district winners reconcile

A concrete law is a composition of six implementations plus validity dates; a reform
proposal is that object with one slot replaced.

Data types are frozen pydantic models (see :mod:`wahlwerk.model`); the six slots are
``runtime_checkable`` protocols, so a law rejects a malformed slot at construction.

Status: M0 -- interfaces only. No slot implementations, no data.
"""

from __future__ import annotations

from wahlwerk.aggregation import AggregatedVotes, AggregationRule
from wahlwerk.apportionment import (
    Allocation,
    ApportionmentMethod,
    Entitlement,
    SeatConstraints,
    SeatTargets,
    TieredApportionment,
)
from wahlwerk.assignment import (
    AssignmentResult,
    AssignmentRule,
    DistrictOutcome,
    DistrictWin,
)
from wahlwerk.ballots import (
    Attachment,
    BallotSection,
    BallotStructure,
    TallyKey,
    TallyRow,
    TurnoutRow,
    VoteTally,
)
from wahlwerk.eligibility import EligibilityFilter, EligibilityVerdict, PartyStanding
from wahlwerk.ids import (
    Candidacy,
    CandidacyKind,
    CandidateId,
    LevelName,
    Nominations,
    Party,
    PartyId,
    Person,
    SectionName,
    UnitId,
)
from wahlwerk.law import SLOTS, ElectoralLaw, LawRegistry
from wahlwerk.mandate import Mandate, MandateSource
from wahlwerk.model import Count, Model, Seats, Share, SlotModel
from wahlwerk.registry import PartyRegistry, german_parties
from wahlwerk.state import Chamber, Fraktion, Government, Term
from wahlwerk.tiers import TierStructure, Unit
from wahlwerk.ties import Tie, TieBreaker, UnresolvedTie

__version__ = "0.1.0"

__all__ = [
    "SLOTS",
    "AggregatedVotes",
    "AggregationRule",
    "Allocation",
    "ApportionmentMethod",
    "AssignmentResult",
    "AssignmentRule",
    "Attachment",
    "BallotSection",
    "BallotStructure",
    "Candidacy",
    "CandidacyKind",
    "CandidateId",
    "Chamber",
    "Count",
    "DistrictOutcome",
    "DistrictWin",
    "ElectoralLaw",
    "EligibilityFilter",
    "EligibilityVerdict",
    "Entitlement",
    "Fraktion",
    "Government",
    "LawRegistry",
    "LevelName",
    "Mandate",
    "MandateSource",
    "Model",
    "Nominations",
    "Party",
    "PartyId",
    "PartyRegistry",
    "PartyStanding",
    "Person",
    "SeatConstraints",
    "SeatTargets",
    "Seats",
    "SectionName",
    "Share",
    "SlotModel",
    "TallyKey",
    "TallyRow",
    "Term",
    "Tie",
    "TieBreaker",
    "TierStructure",
    "TieredApportionment",
    "TurnoutRow",
    "Unit",
    "UnitId",
    "UnresolvedTie",
    "VoteTally",
    "__version__",
    "german_parties",
]
