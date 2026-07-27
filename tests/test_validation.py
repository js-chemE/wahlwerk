"""What the models refuse to be constructed with.

Every rule here is an invariant that would otherwise surface as a wrong seat count
several stages downstream. Pydantic turns each into a failure at the point the bad
value enters the system -- which, for election data, is the moment a reader parses a
row out of a Landeswahlleiter file.
"""

from __future__ import annotations

from datetime import date
from fractions import Fraction

import pytest
from pydantic import ValidationError

from wahlwerk import (
    Attachment,
    BallotSection,
    Candidacy,
    CandidacyKind,
    LevelName,
    Nominations,
    PartyStanding,
    SectionName,
    TallyKey,
    TallyRow,
    Tie,
    Unit,
    UnitId,
    VoteTally,
)
from wahlwerk.apportionment import SeatConstraints, SeatTargets
from wahlwerk.ids import BodyId, CandidateId, PartyId
from wahlwerk.state import Term


def test_a_vote_count_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        TallyRow(
            unit=UnitId("wk.001"),
            section=SectionName("zweitstimme"),
            party=PartyId("cdu"),
            count=-1,
        )


def test_a_count_names_a_party_or_a_candidate_but_not_both() -> None:
    with pytest.raises(ValidationError, match="not both and not neither"):
        TallyKey(unit=UnitId("wk.001"), section=SectionName("z"))
    with pytest.raises(ValidationError, match="not both and not neither"):
        TallyKey(
            unit=UnitId("wk.001"),
            section=SectionName("z"),
            party=PartyId("cdu"),
            candidate=CandidateId("p1"),
        )


def test_a_tally_refuses_two_rows_for_the_same_key() -> None:
    row = TallyRow(
        unit=UnitId("wk.001"),
        section=SectionName("zweitstimme"),
        party=PartyId("cdu"),
        count=100,
    )
    with pytest.raises(ValidationError, match="duplicate tally row"):
        VoteTally(rows=(row, row.model_copy(update={"count": 200})))


def test_an_unknown_column_is_an_error_not_a_shrug() -> None:
    """Sixteen Landeswahlleiter, sixteen sets of column names. This is the tripwire."""
    with pytest.raises(ValidationError, match=r"[Ee]xtra"):
        TallyRow(
            unit=UnitId("wk.001"),
            section=SectionName("zweitstimme"),
            party=PartyId("cdu"),
            count=100,
            stimmen=100,  # type: ignore[call-arg]
        )


def test_cumulation_cannot_exceed_the_votes_a_voter_has() -> None:
    with pytest.raises(ValidationError, match="cannot pile 5 marks"):
        BallotSection(
            name=SectionName("landesstimmen"),
            level=LevelName("land"),
            attaches_to=Attachment.CANDIDATE,
            votes_per_voter=3,
            max_per_target=5,
        )


def test_a_single_vote_cannot_be_panaschiert() -> None:
    with pytest.raises(ValidationError, match="panaschiert"):
        BallotSection(
            name=SectionName("erststimme"),
            level=LevelName("wahlkreis"),
            attaches_to=Attachment.CANDIDATE,
            panachage=True,
        )


def test_a_district_contest_cannot_be_decided_by_a_party_vote() -> None:
    with pytest.raises(ValidationError, match="won by a person"):
        BallotSection(
            name=SectionName("zweitstimme"),
            level=LevelName("wahlkreis"),
            attaches_to=Attachment.PARTY,
            decides_district=True,
        )


def test_hamburg_is_a_perfectly_legal_ballot_section() -> None:
    section = BallotSection(
        name=SectionName("landesstimmen"),
        level=LevelName("land"),
        attaches_to=Attachment.EITHER,
        votes_per_voter=5,
        max_per_target=5,
        panachage=True,
    )
    assert section.max_per_target == 5


def test_a_tie_needs_more_contenders_than_seats() -> None:
    with pytest.raises(ValidationError, match="is not a tie"):
        Tie(contenders=frozenset({"cdu", "spd"}), seats=2)
    with pytest.raises(ValidationError):
        Tie(contenders=frozenset({"cdu"}), seats=1)


def test_a_unit_cannot_be_its_own_parent() -> None:
    with pytest.raises(ValidationError, match="own parent"):
        Unit(
            id=UnitId("de.bund.land.01"),
            name="Schleswig-Holstein",
            level=LevelName("land"),
            parent=UnitId("de.bund.land.01"),
        )


def test_a_district_candidacy_has_no_list_position() -> None:
    with pytest.raises(ValidationError, match="no list position"):
        Candidacy(
            candidate=CandidateId("p1"),
            unit=UnitId("wk.001"),
            kind=CandidacyKind.DISTRICT,
            list_position=1,
        )


def test_list_positions_are_one_based() -> None:
    with pytest.raises(ValidationError, match="1-based"):
        Candidacy(
            candidate=CandidateId("p1"),
            unit=UnitId("land.01"),
            kind=CandidacyKind.LIST,
            list_position=0,
        )


def test_nominations_refuse_the_same_candidacy_twice() -> None:
    c = Candidacy(
        candidate=CandidateId("p1"), unit=UnitId("wk.001"), kind=CandidacyKind.DISTRICT
    )
    with pytest.raises(ValidationError, match="duplicate candidacy"):
        Nominations(candidacies=(c, c))


def test_a_list_comes_back_in_the_order_it_was_filed() -> None:
    def cand(who: str, pos: int) -> Candidacy:
        return Candidacy(
            candidate=CandidateId(who),
            unit=UnitId("land.01"),
            kind=CandidacyKind.LIST,
            party=PartyId("spd"),
            list_position=pos,
        )

    nominations = Nominations(candidacies=(cand("c", 3), cand("a", 1), cand("b", 2)))
    order = [c.candidate for c in nominations.list_of(PartyId("spd"), UnitId("land.01"))]
    assert order == ["a", "b", "c"]


def test_an_admitted_party_must_say_what_carried_it() -> None:
    with pytest.raises(ValidationError, match="record which one carried it"):
        PartyStanding(party=PartyId("fdp"), admitted=True, share=Fraction(3, 100))


def test_the_grundmandatsklausel_is_a_recorded_exemption() -> None:
    standing = PartyStanding(
        party=PartyId("linke"),
        admitted=True,
        share=Fraction(48, 1000),
        threshold_met=False,
        exemption="grundmandatsklausel",
    )
    assert standing.exemption == "grundmandatsklausel"


def test_a_share_is_exact_and_bounded() -> None:
    with pytest.raises(ValidationError):
        PartyStanding(party=PartyId("x"), admitted=False, share=Fraction(3, 2))


def test_seat_targets_reject_a_cap_below_the_minimum() -> None:
    with pytest.raises(ValidationError, match="below minimum"):
        SeatTargets(minimum=120, cap=100)


def test_constraints_reject_an_unsatisfiable_key() -> None:
    with pytest.raises(ValidationError, match="minimum 5 exceeds maximum 3"):
        SeatConstraints(minimums={"cdu": 5}, maximums={"cdu": 3})


def test_a_term_cannot_end_before_it_starts() -> None:
    with pytest.raises(ValidationError, match="precedes start"):
        Term(
            body=BodyId("de.bund.bundestag"),
            start=date(2025, 3, 25),
            scheduled_end=date(2024, 1, 1),
        )


def test_models_are_frozen() -> None:
    tie = Tie(contenders=frozenset({"a", "b"}), seats=1)
    with pytest.raises(ValidationError):
        tie.seats = 2


def test_an_identifier_that_is_not_a_lowercase_dotted_key_is_rejected() -> None:
    """The scheme in `ids.py` is enforced, not merely documented."""
    for bad in ("de.bund.Bundestag", "de..bund", "de bund", "de.bund.", "", "DE.BUND"):
        with pytest.raises(ValidationError):
            Term(body=BodyId(bad), start=date(2025, 3, 25))


def test_a_body_id_survives_the_shapes_actually_in_use() -> None:
    for good in ("de.bund.bundestag", "de.by.landtag", "de.hh.buergerschaft"):
        assert Term(body=BodyId(good), start=date(2025, 3, 25)).body == good


def test_an_umlaut_in_an_identifier_is_rejected() -> None:
    """Identifiers transliterate; only prose and data carry umlauts."""
    with pytest.raises(ValidationError):
        Term(body=BodyId("de.bund.aufloesung.prüfung"), start=date(2025, 3, 25))
