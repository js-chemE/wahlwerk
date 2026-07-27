"""The party registry: one stable id per party, and every name it is ever called.

Sixteen Landeswahlleiter spell the same party six different ways -- ``GRÜNE``,
``BÜNDNIS 90/DIE GRÜNEN``, ``B90/GRÜNE``, ``Grüne`` -- and the Bundeswahlleiterin
refers to it by the number 3. Merging sources is therefore an *alias resolution*
problem before it is anything else, and it is the first thing that breaks silently: an
unrecognised spelling becomes a phantom party with 12 % of the vote and no seats.

So aliases are their own long table, exactly like the vote tally:

    party,source,key
    gruene,bundeswahlleiterin.gruppe,3
    gruene,bundeswahlleiterin.name,GRÜNE
    gruene,common,B90/GRÜNE

A reader looks up ``registry.resolve("3", source="bundeswahlleiterin.gruppe")`` and
gets a :class:`~wahlwerk.ids.Party`, or a :class:`LookupError` naming the key it could
not place. There is no fallback to fuzzy matching -- an unknown spelling is a data
question for a human, not something to guess at.

The shipped German registry is seeded from the Bundeswahlleiterin's BTW 2025 open data
(``gesamtergebnis_01.xml``), whose ``Gruppe`` numbers are the ``bundeswahlleiterin.gruppe``
source. Long names are filled in where they are verified; where they are not, the
official short designation is repeated rather than guessed at.
"""

from __future__ import annotations

import csv
from functools import cache, cached_property
from importlib.resources import files
from typing import Literal

from pydantic import model_validator

from wahlwerk.ids import DottedKey, Party, PartyId
from wahlwerk.model import Model

__all__ = ["PartyAlias", "PartyRegistry", "german_parties"]

Country = Literal["de"]


def _normalise(key: str) -> str:
    """Fold a spelling to its comparison form. Case and padding only -- never letters.

    Deliberately does not strip umlauts or punctuation: ``GRÜNE`` and ``GRUENE`` are
    two aliases to be recorded, not one to be inferred.
    """
    return " ".join(key.split()).casefold()


class PartyAlias(Model):
    """One name, in one source, for one party."""

    party: PartyId
    source: DottedKey
    """Where the spelling comes from: ``bundeswahlleiterin.gruppe``,
    ``bundeswahlleiterin.name``, ``landeswahlleiter.by.name``, or ``common`` for
    spellings in general circulation."""

    key: str

    @property
    def lookup(self) -> tuple[str, str]:
        return self.source, _normalise(self.key)


class PartyRegistry(Model):
    """Parties and their aliases."""

    parties: tuple[Party, ...] = ()
    aliases: tuple[PartyAlias, ...] = ()

    @model_validator(mode="after")
    def _check_consistent(self) -> PartyRegistry:
        ids = [p.id for p in self.parties]
        if len(set(ids)) != len(ids):
            duplicates = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"duplicate party ids: {duplicates}")
        known = set(ids)
        placed: dict[tuple[str, str], PartyId] = {}
        for alias in self.aliases:
            if alias.party not in known:
                raise ValueError(f"alias {alias.key!r} points at unknown party {alias.party!r}")
            owner = placed.get(alias.lookup)
            if owner is not None and owner != alias.party:
                raise ValueError(
                    f"{alias.source}:{alias.key!r} is claimed by both "
                    f"{owner!r} and {alias.party!r}"
                )
            placed[alias.lookup] = alias.party
        return self

    @cached_property
    def by_id(self) -> dict[PartyId, Party]:
        return {p.id: p for p in self.parties}

    @cached_property
    def _by_alias(self) -> dict[tuple[str, str], PartyId]:
        return {alias.lookup: alias.party for alias in self.aliases}

    @cached_property
    def _by_key(self) -> dict[str, set[PartyId]]:
        """Every spelling, regardless of source -- used only when no source is given."""
        index: dict[str, set[PartyId]] = {}
        for alias in self.aliases:
            index.setdefault(_normalise(alias.key), set()).add(alias.party)
        for party in self.parties:
            for spelling in (party.id, party.name, party.short_name):
                if spelling:
                    index.setdefault(_normalise(spelling), set()).add(party.id)
        return index

    def __len__(self) -> int:
        return len(self.parties)

    def __contains__(self, party_id: str) -> bool:
        return party_id in self.by_id

    def get(self, party_id: str) -> Party:
        """Look up by stable id. Raises :class:`KeyError`."""
        try:
            return self.by_id[PartyId(party_id)]
        except KeyError:
            raise KeyError(f"no party {party_id!r} in registry") from None

    def resolve(self, key: str | int, source: str | None = None) -> Party:
        """Turn a spelling from a source file into a party.

        With ``source`` given the lookup is exact and unambiguous. Without it, every
        recorded spelling is searched and an ambiguous hit raises rather than picking
        one -- which is what you want when merging sixteen Länder.
        """
        text = str(key)
        if source is not None:
            found = self._by_alias.get((source, _normalise(text)))
            if found is None:
                raise LookupError(f"{source} has no party {text!r} in this registry")
            return self.by_id[found]
        candidates = self._by_key.get(_normalise(text), set())
        if not candidates:
            raise LookupError(f"no party matches {text!r} in any recorded source")
        if len(candidates) > 1:
            raise LookupError(
                f"{text!r} is ambiguous between {sorted(candidates)} -- pass a source"
            )
        return self.by_id[next(iter(candidates))]

    def tagged(self, tag: str) -> tuple[Party, ...]:
        """Parties carrying a tag, e.g. ``national_minority`` for slot 4."""
        return tuple(p for p in self.parties if tag in p.tags)

    def aliases_of(self, party_id: str) -> tuple[PartyAlias, ...]:
        return tuple(a for a in self.aliases if a.party == party_id)

    def merge(self, other: PartyRegistry) -> PartyRegistry:
        """Combine two registries. Re-validated, so a conflicting alias is an error."""
        seen = {p.id for p in self.parties}
        return PartyRegistry(
            parties=self.parties + tuple(p for p in other.parties if p.id not in seen),
            aliases=self.aliases + other.aliases,
        )


def _read_csv(name: str) -> list[dict[str, str]]:
    text = files("wahlwerk.data").joinpath(name).read_text(encoding="utf-8")
    return list(csv.DictReader(text.splitlines()))


@cache
def german_parties() -> PartyRegistry:
    """The registry shipped with the package, seeded from Bundeswahlleiterin open data.

    >>> german_parties().resolve(3, source="bundeswahlleiterin.gruppe").short_name
    'GRÜNE'
    """
    parties = tuple(
        Party(
            id=PartyId(row["id"]),
            name=row["name"],
            short_name=row["short_name"],
            tags=frozenset(row["tags"].split()),
        )
        for row in _read_csv("parties_de.csv")
    )
    aliases = tuple(
        PartyAlias(party=PartyId(row["party"]), source=row["source"], key=row["key"])
        for row in _read_csv("party_aliases_de.csv")
    )
    return PartyRegistry(parties=parties, aliases=aliases)
