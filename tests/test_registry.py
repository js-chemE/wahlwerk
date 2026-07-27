"""The party registry, and the alias problem it exists to solve."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from wahlwerk.ids import Party, PartyId
from wahlwerk.registry import PartyAlias, PartyRegistry, german_parties

BWL_GRUPPE = "bundeswahlleiterin.gruppe"
BWL_NAME = "bundeswahlleiterin.name"


def test_the_shipped_registry_loads() -> None:
    registry = german_parties()
    assert len(registry) >= 30
    assert "cdu" in registry
    assert registry.get("spd").name == "Sozialdemokratische Partei Deutschlands"


def test_the_bundeswahlleiterin_gruppe_numbers_resolve() -> None:
    """Straight out of gesamtergebnis_01.xml: Gruppe="3" Gruppenart="PARTEI"."""
    registry = german_parties()
    assert registry.resolve(1, source=BWL_GRUPPE).id == "cdu"
    assert registry.resolve(2, source=BWL_GRUPPE).id == "spd"
    assert registry.resolve(3, source=BWL_GRUPPE).id == "gruene"
    assert registry.resolve(4, source=BWL_GRUPPE).id == "linke"
    assert registry.resolve(5, source=BWL_GRUPPE).id == "afd"
    assert registry.resolve(6, source=BWL_GRUPPE).id == "csu"
    assert registry.resolve(59, source=BWL_GRUPPE).id == "ssw"
    assert registry.resolve(64, source=BWL_GRUPPE).id == "bsw"


def test_the_same_party_under_six_spellings() -> None:
    registry = german_parties()
    spellings = [
        "GRÜNE",
        "BÜNDNIS 90/DIE GRÜNEN",
        "B90/GRÜNE",
        "Bündnis 90/Die Grünen",
        "GRUENE",
        "grüne",
    ]
    assert {registry.resolve(s).id for s in spellings} == {"gruene"}


def test_lookup_is_case_and_whitespace_insensitive_but_nothing_more() -> None:
    registry = german_parties()
    assert registry.resolve("  freie   wähler  ").id == "fw"
    with pytest.raises(LookupError):
        registry.resolve("Freie Waehler")  # not a recorded spelling -- ask a human


def test_an_unknown_spelling_raises_rather_than_guessing() -> None:
    with pytest.raises(LookupError, match="no party matches"):
        german_parties().resolve("Die Grunen Partei")


def test_an_unknown_key_in_a_known_source_names_the_source() -> None:
    with pytest.raises(LookupError, match=BWL_GRUPPE):
        german_parties().resolve(9999, source=BWL_GRUPPE)


def test_the_ssw_is_tagged_for_the_slot_4_exemption() -> None:
    minorities = german_parties().tagged("national_minority")
    assert [p.id for p in minorities] == ["ssw"]


def test_uebrige_is_marked_as_an_aggregate_not_a_party() -> None:
    """Gruppe 28 is a residual bucket. A reader must be able to tell."""
    registry = german_parties()
    assert "aggregate" in registry.get("uebrige").tags
    assert registry.resolve(28, source=BWL_GRUPPE).id == "uebrige"


def test_cdu_and_csu_are_two_parties() -> None:
    """The Fraktionsgemeinschaft lives in Fraktion, never here."""
    registry = german_parties()
    assert registry.get("cdu").id != registry.get("csu").id
    assert registry.resolve("CDU", source=BWL_NAME).id == "cdu"
    assert registry.resolve("CSU", source=BWL_NAME).id == "csu"


def test_every_alias_points_at_a_party_that_exists() -> None:
    registry = german_parties()
    known = {p.id for p in registry.parties}
    assert {a.party for a in registry.aliases} <= known


def test_a_registry_refuses_an_alias_two_parties_claim() -> None:
    parties = (Party(id=PartyId("a"), name="A"), Party(id=PartyId("b"), name="B"))
    aliases = (
        PartyAlias(party=PartyId("a"), source="x", key="shared"),
        PartyAlias(party=PartyId("b"), source="x", key="SHARED"),
    )
    with pytest.raises(ValidationError, match="claimed by both"):
        PartyRegistry(parties=parties, aliases=aliases)


def test_a_registry_refuses_an_alias_for_an_unknown_party() -> None:
    with pytest.raises(ValidationError, match="unknown party"):
        PartyRegistry(
            parties=(Party(id=PartyId("a"), name="A"),),
            aliases=(PartyAlias(party=PartyId("ghost"), source="x", key="k"),),
        )


def test_registries_merge_and_stay_consistent() -> None:
    extra = PartyRegistry(
        parties=(
            Party(id=PartyId("ssw"), name="ignored"),
            Party(id=PartyId("new"), name="New"),
        ),
        aliases=(PartyAlias(party=PartyId("new"), source="landeswahlleiter.sh", key="NEU"),),
    )
    merged = german_parties().merge(extra)
    assert merged.resolve("NEU", source="landeswahlleiter.sh").id == "new"
    assert merged.get("ssw").name == "Südschleswigscher Wählerverband", "existing wins"


def test_the_registry_covers_every_party_that_has_held_a_bundestag_seat() -> None:
    """One collection, not a current-parliament snapshot.

    The registry is seeded from BTW 2025 but is the single namespace authority for the
    whole archive, so the groupings that last sat in the 1950s belong in it too. If a
    bundle could mint its own ids, nothing would notice when two disagreed.
    """
    registry = german_parties()
    for party_id in ("dp", "kpd", "wav", "zentrum", "gb-bhe", "dkp-drp", "andere-kwv"):
        assert party_id in registry, f"{party_id} held seats and is not in the registry"
    assert registry.get("gb-bhe").short_name == "GB/BHE"


def test_the_1990_ost_list_is_the_same_party_as_the_gruene() -> None:
    """B90/Gr and DIE GRÜNEN ran as separate lists in 1990 and merged in 1993.

    They get one id: the distinction that year was *territorial* -- the threshold applied
    separately to the two Wahlgebiete -- and the tier structure already carries territory.
    Two lists in two Wahlgebiete are two units, not two parties.
    """
    registry = german_parties()
    assert registry.resolve("B90/Gr", source=BWL_NAME).id == "gruene"
    assert registry.resolve("BÜNDNIS 90/GRÜNE").id == "gruene"


def test_the_residual_bucket_is_tagged_like_the_other_one() -> None:
    """ "Andere Kreiswahlvorschläge" is not a party, and neither is Übrige."""
    registry = german_parties()
    assert {p.id for p in registry.tagged("aggregate")} == {"uebrige", "andere-kwv"}
