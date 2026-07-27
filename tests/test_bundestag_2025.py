"""The 21st Bundestag as reconstructed in ``examples/bundestag_2025.py``.

Not a golden test -- nothing is derived here, the seat distribution is typed in from
the published result. It is the *target* the M1 golden test will assert against once
BWahlG-2023 runs over real constituency votes.
"""

from __future__ import annotations

from datetime import date

import pytest

from wahlwerk.examples.bundestag_2025 import CONSTITUTED, SEATS, build
from wahlwerk.mandate import MandateSource
from wahlwerk.registry import german_parties
from wahlwerk.state import Chamber


@pytest.fixture(scope="module")
def chamber() -> Chamber:
    return build()


def test_the_chamber_has_exactly_630_seats(chamber: Chamber) -> None:
    assert chamber.size == 630
    assert sum(SEATS.values()) == 630


def test_the_seat_distribution_matches_the_published_result(chamber: Chamber) -> None:
    assert chamber.seats_by_party == {
        "cdu": 164,
        "afd": 152,
        "spd": 120,
        "gruene": 85,
        "linke": 64,
        "csu": 44,
        "ssw": 1,
    }


def test_every_party_holding_a_seat_is_in_the_registry(chamber: Chamber) -> None:
    registry = german_parties()
    holders = [p for p in chamber.seats_by_party if p is not None]
    assert len(holders) == len(chamber.seats_by_party), "no independents in this chamber"
    for party_id in holders:
        assert registry.get(party_id).short_name


def test_provenance_is_recorded_as_absent_not_invented(chamber: Chamber) -> None:
    """The published Sitzverteilung says nothing per seat, and the model says so."""
    assert {m.source for m in chamber.mandates} == {MandateSource.UNRECORDED}
    assert all(m.person is None for m in chamber.mandates)
    assert all(m.unit is None and m.level is None for m in chamber.mandates)
    assert len(chamber.vacant_seats) == 630


def test_seat_keys_are_unique(chamber: Chamber) -> None:
    assert len({m.seat for m in chamber.mandates}) == 630


def test_cdu_and_csu_sit_in_one_fraktion_as_two_parties(chamber: Chamber) -> None:
    union = next(f for f in chamber.fraktionen if f.id == "cdu-csu")
    assert union.parties == frozenset({"cdu", "csu"})
    assert union.is_gemeinschaft
    assert union.size == 164 + 44 == 208


def test_the_fraktionen_account_for_629_of_630_seats(chamber: Chamber) -> None:
    grouped = sum(f.size for f in chamber.fraktionen)
    assert grouped == 629
    assert chamber.size - grouped == 1, "the SSW member is fraktionslos"


def test_every_fraktion_clears_the_go_bt_threshold(chamber: Chamber) -> None:
    """Sec. 10 (1) GO-BT: five per cent of 630 members is 32."""
    threshold = 32
    assert all(f.recognised for f in chamber.fraktionen)
    assert min(f.size for f in chamber.fraktionen) >= threshold
    assert SEATS["ssw"] < threshold, "which is why the SSW member sits alone"


def test_the_term_is_the_21st_wahlperiode(chamber: Chamber) -> None:
    assert chamber.term.number == 21
    assert chamber.term.start == CONSTITUTED == date(2025, 3, 25)
    assert not chamber.term.ended
