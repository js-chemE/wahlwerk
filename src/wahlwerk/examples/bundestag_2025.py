"""The 21st Bundestag as a `Chamber` -- 630 seats, built from the published result.

This is *not* an election. Nothing here is derived: the seat distribution is typed in
from the Bundeswahlleiterin's endgültiges Ergebnis for the Bundestagswahl of
23 February 2025, and the example turns those seven numbers into 630 individual
mandates. M1 will produce exactly this chamber from constituency-level votes under
BWahlG-2023, and this file is what it will be asserted against.

What the source gives us, and what it does not:

  * per party, how many seats  -- so every ``Mandate`` carries a party
  * nothing per seat           -- so ``person``, ``unit`` and ``level`` stay unset and
                                  ``source`` is ``MandateSource.UNRECORDED``

Recording the absence rather than inventing plausible names is the whole point. A
golden test must never accept ``UNRECORDED``: an engine that derived a seat knows where
it came from.

Fraktionen are a separate layer over the same mandates, and the 21st Bundestag shows
why they cannot be collapsed into parties:

  * CDU and CSU are two parties in one Fraktionsgemeinschaft of 208
  * the SSW's single member is fraktionslos -- Sec. 10 (1) GO-BT wants 5 % of members,
    which is 32 of 630

Run it:  ``uv run python -m wahlwerk.examples.bundestag_2025``
"""

from __future__ import annotations

from datetime import date

from wahlwerk.ids import BodyId, PartyId
from wahlwerk.mandate import Mandate, MandateSource
from wahlwerk.registry import PartyRegistry, german_parties
from wahlwerk.state import Chamber, Fraktion, Term

BODY = BodyId("de.bund.bundestag")
ELECTION_DAY = date(2025, 2, 23)
CONSTITUTED = date(2025, 3, 25)

SOURCE = (
    "Die Bundeswahlleiterin, Bundestagswahl 2025, endgültiges Ergebnis "
    "(Datenlizenz Deutschland dl-de/by-2-0)"
)

SEATS: dict[str, int] = {
    "cdu": 164,
    "afd": 152,
    "spd": 120,
    "gruene": 85,
    "linke": 64,
    "csu": 44,
    "ssw": 1,
}
"""Sitzverteilung as published. Ordered by size, which is also the order seats are
numbered below -- the physical seating plan of the chamber is not modelled."""

FRAKTIONEN: dict[str, tuple[str, tuple[str, ...]]] = {
    "cdu-csu": ("CDU/CSU", ("cdu", "csu")),
    "afd": ("AfD", ("afd",)),
    "spd": ("SPD", ("spd",)),
    "gruene": ("BÜNDNIS 90/DIE GRÜNEN", ("gruene",)),
    "linke": ("Die Linke", ("linke",)),
}
"""Parties that grouped. The SSW did not -- one member is below any threshold."""

GO_BT_FRAKTION_SHARE = (5, 100)
"""Sec. 10 (1) GO-BT: a Fraktion needs at least five per cent of the members."""


def build(registry: PartyRegistry | None = None) -> Chamber:
    """The 21st Bundestag, seat by seat."""
    registry = registry or german_parties()
    for party_id in SEATS:
        registry.get(party_id)  # fail loudly on a party the registry does not know

    term = Term(body=BODY, start=CONSTITUTED, number=21)

    mandates: list[Mandate] = []
    for party_id, seats in SEATS.items():
        for n in range(1, seats + 1):
            mandates.append(
                Mandate(
                    seat=f"de.bund.btw25.{party_id}.{n:03d}",
                    party=PartyId(party_id),
                    source=MandateSource.UNRECORDED,
                    since=CONSTITUTED,
                )
            )

    threshold = -(-len(mandates) * GO_BT_FRAKTION_SHARE[0] // GO_BT_FRAKTION_SHARE[1])
    fraktionen = tuple(
        Fraktion(
            id=fraktion_id,
            name=name,
            parties=frozenset(PartyId(p) for p in parties),
            declared_size=sum(SEATS[p] for p in parties),
            recognised=sum(SEATS[p] for p in parties) >= threshold,
            since=CONSTITUTED,
        )
        for fraktion_id, (name, parties) in FRAKTIONEN.items()
    )

    return Chamber(body=BODY, term=term, mandates=tuple(mandates), fraktionen=fraktionen)


def main() -> None:
    registry = german_parties()
    chamber = build(registry)
    grouped = {p for f in chamber.fraktionen for p in f.parties}

    print(f"{chamber.body}  --  {chamber.term.number}. Wahlperiode")
    print(f"elected {ELECTION_DAY.isoformat()}, constituted {CONSTITUTED.isoformat()}")
    print(f"{chamber.size} seats\n")

    print("by party")
    for party_id, seats in sorted(SEATS.items(), key=lambda kv: -kv[1]):
        party = registry.get(party_id)
        tags = f"  [{' '.join(sorted(party.tags))}]" if party.tags else ""
        print(f"  {party.short_name:<12} {seats:>4}{tags}")

    print("\nby Fraktion")
    for fraktion in sorted(chamber.fraktionen, key=lambda f: -f.size):
        note = " (Fraktionsgemeinschaft)" if fraktion.is_gemeinschaft else ""
        print(f"  {fraktion.name:<24} {fraktion.size:>4}{note}")
    loose = sum(seats for p, seats in SEATS.items() if p not in grouped)
    print(f"  {'fraktionslos':<24} {loose:>4}")

    print(f"\nsource: {SOURCE}")


if __name__ == "__main__":
    main()
