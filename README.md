# wahlwerk

German electoral and parliamentary systems as **rules-as-code**: a deterministic engine
parameterised by an electoral law, so that small changes to the law can be evaluated
against real historical votes.

Scope covers all three levels — Bundestag, Landtage, kommunale Vertretungen — plus the
derived bodies (Bundesrat) and the veto structure connecting them.

> **Status: M0 — interfaces only.** The six slot protocols, `ElectoralLaw`, the
> state/event types, the party registry and the archive reader exist. There is **no law
> implementation yet**, so nothing is *derived*: `Chamber.from_archive("de.bund.2025")`
> reads the published result, it does not compute one. See [Build order](#build-order).

## Repositories

Three, split along the lines that actually differ — licence, size and change cadence:

| Repo | Holds | Why separate |
|---|---|---|
| [**wahlwerk**](https://github.com/js-chemE/wahlwerk) | the engine | Apache-2.0, small, `pip install`-able |
| [**wahlwerk-data**](https://github.com/js-chemE/wahlwerk-data) | normalised election bundles | dl-de/by-2-0, grows per election, must never bloat the engine's clone |
| [**wahlwerk-execute**](https://github.com/js-chemE/wahlwerk-execute) | notebooks and analyses | depends on both; its output is figures, not a library |

The engine does **not** depend on the data repo, and its test suite passes with the
archive absent — anything that reads a bundle builds a synthetic one in a `tmp_path`, and
the real archive is exercised on the other side, in wahlwerk-data's own tests. When golden
tests arrive at M1 their fixtures will be committed here under `tests/golden/`, small and
gzipped, so **CI runs offline and a golden test never fails for network reasons**.

`wahlwerk-data` is the *archive*: every Bundestagswahl since 1949, sixteen Länder,
kommunal. To use it, clone it and let the engine find it:

```bash
git clone https://github.com/js-chemE/wahlwerk-data.git   # beside this repo
```

Resolution order, first hit wins:

```
$WAHLWERK_DATA          explicit — what CI and containers set
../wahlwerk-data        a sibling clone, searched upwards from the cwd
~/.cache/wahlwerk/data  a fetched copy, once scripts/fetch_data.py exists
```

So **cloning `wahlwerk-data` beside `wahlwerk` is convenient, not required** — it is just
what makes the middle path work with no configuration. `wahlwerk.io.find_archive` reports
every path it searched if none is found.

Bundles carry `schema = N` in their `election.toml` and the engine declares which
versions it reads, so a format change is a loud, testable break rather than a silent
mis-parse. `wahlwerk-data` tags releases; an analysis pins an engine version and a data
tag together, which is what makes a reproduction reproducible.

## The six slots

Every electoral law in scope decomposes into six orthogonal components. That
decomposition *is* the modularity of the package; a concrete law is a composition of six
implementations plus validity dates.

| # | Module | Question it answers | The case that stresses it |
|---|---|---|---|
| 1 | [`tiers.py`](src/wahlwerk/tiers.py) | How does territory map to allocation units, and how do they nest? | Bayern: Stimmkreis → Wahlkreis → Land |
| 2 | [`ballots.py`](src/wahlwerk/ballots.py) | How many votes, attached to what? | Hamburg: 5+5 votes, kumuliert und panaschiert, attached to people |
| 3 | [`aggregation.py`](src/wahlwerk/aggregation.py) | Which votes feed the proportional entitlement? | Bayern: Erst- **and** Zweitstimmen summed |
| 4 | [`eligibility.py`](src/wahlwerk/eligibility.py) | Threshold, at which tier, with which exemptions? | Bund: 5 % **or** Grundmandatsklausel **or** nationale Minderheit |
| 5 | [`apportionment/`](src/wahlwerk/apportionment/) | Which divisor or quota method, and in what tier order? | Federal two-tier linkage |
| 6 | [`assignment.py`](src/wahlwerk/assignment.py) | Who occupies the seats? | Zweitstimmendeckung (Bund) vs. Überhang + Ausgleich (BW) |

A reform proposal is a law object with one slot replaced:

```python
dhondt_variant = bwahlg_2023.variant(apportionment=dhondt_rule)
no_grundmandat = bwahlg_2023.variant(eligibility=pure_five_percent)
```

That is the whole counterfactual mechanism.

`apportionment/` contains **zero German-specific content** — it takes opaque keys, vote
counts and a seat total. If a Land quirk leaks in there, the abstraction is broken.

## Language

English is the language of code; German electoral law is the subject matter. The rule
that keeps both honest:

> **Translate the concept. Keep the term of art.**

A term is *of art* if translating it would lose a distinction the law makes, or if you
would have to invent the English. Everything else is English.

| Keep German | Use English | Why |
|---|---|---|
| `Zweitstimme`, `Erststimme` | ~~second vote~~ | "second" sounds like ordering; it names a function |
| `Wahlkreis`, `Stimmkreis`, `Wahlbezirk` | ~~constituency~~ | English has one word for three legally distinct things |
| `Überhang`, `Ausgleich`, `Grundmandatsklausel` | — | no English equivalent exists |
| `Fraktion` | ~~parliamentary group~~ | a Fraktion is defined by GO-BT, not by translation |
| `Nachrücken`, `Wahlprüfung`, `Auflösung` | — | named procedures in statute |
| — | `party`, `seat`, `unit`, `count`, `share` | the same concept in every country |

The test: **does an official source use this word?** If the Bundeswahlleiterin, a
statute or the BVerfG says it, keep it. If you had to reach for a dictionary, you are
inventing vocabulary nobody else uses.

**Orthography.** Identifiers and filenames are ASCII-transliterated (`ue`, `oe`, `ae`,
`ss`) so they stay greppable and typeable on any keyboard. Prose, data and output use
correct German:

```python
# wahlwerk/events/aufloesung.py
class Aufloesung(Model):
    """Auflösung under Art. 68 GG: the term ends early."""
```

Sphinx roles name the *identifier*, so ``:class:`Aufloesung` `` stays ASCII while the
sentence around it does not. `ruff` catches the mistake that matters — an `__all__`
entry that no longer names anything is `F822`.

**Everything else is English**: docstrings, comments, test names, commit messages,
error messages, and this README. A German reader knows English; nobody outside knows
what a `Zweitstimmendeckung` is either way, so the docstring explains it.

**Legal citations** stay in the German form with an English gloss on first use, and
always with the section: `Sec. 10 (1) GO-BT`, `Art. 68 GG`, `Sec. 4 (2) BWahlG`.
Judgments carry their docket: `BVerfG, 2 BvF 1/23`.

## Identifiers

Every stable key is a lowercase ASCII dotted path, narrowest scope last. The scheme is
enforced in [`ids.py`](src/wahlwerk/ids.py) — each id is a `NewType` over a
pattern-constrained string, so `de.bund.Bundestag` fails validation where it is written,
and mypy still refuses to pass a `PartyId` where a `UnitId` belongs.

| Type | Shape | Examples |
|---|---|---|
| `BodyId` | dotted | `de.bund.bundestag`, `de.by.landtag` |
| `LawId` | dotted, `+slot` for variants | `de.bund.bwahlg.2023`, `de.bund.bwahlg.2023+apportionment` |
| `UnitId` | dotted | `de.bund.land.01`, `de.bund.wk.001` |
| `PartyId` | dotted | `cdu`, `gruene`, `team-todenhoefer` |
| `LevelName` | single segment | `wahlkreis`, `land`, `bund` |
| `SectionName` | single segment | `erststimme`, `zweitstimme` |

**Bodies** are named by jurisdiction then institution. `de.bund` is the federation;
the sixteen Länder use their official two-letter code:

| | Body | | Body |
|---|---|---|---|
| Bund | `de.bund.bundestag` | | `de.bund.bundesrat` |
| BW | `de.bw.landtag` | NI | `de.ni.landtag` |
| BY | `de.by.landtag` | NW | `de.nw.landtag` |
| BE | `de.be.abgeordnetenhaus` | RP | `de.rp.landtag` |
| BB | `de.bb.landtag` | SL | `de.sl.landtag` |
| HB | `de.hb.buergerschaft` | SN | `de.sn.landtag` |
| HH | `de.hh.buergerschaft` | ST | `de.st.landtag` |
| HE | `de.he.landtag` | SH | `de.sh.landtag` |
| MV | `de.mv.landtag` | TH | `de.th.landtag` |

Three Länder do not call their parliament a Landtag, which is why the institution is
named rather than assumed: Berlin has an Abgeordnetenhaus, Bremen and Hamburg have a
Bürgerschaft. Municipal bodies extend the same path —
`de.nw.koeln.rat`, `de.by.muenchen.stadtrat`.

A `BodyId` is only a key. The institution *model* — name, jurisdiction, Bundesrat vote
weight, election calendar — arrives with M6, when the Bundesrat needs the sixteen Länder
as data rather than as strings.

## Party registry

One stable id per party, and every name it is ever called. Merging sixteen
Landeswahlleiter is an alias-resolution problem before it is anything else — an
unrecognised spelling silently becomes a phantom party with 12 % of the vote and no
seats. So aliases are their own long table, seeded from the Bundeswahlleiterin's BTW
2025 open data:

```python
from wahlwerk.registry import german_parties

r = german_parties()
r.resolve(3, source="bundeswahlleiterin.gruppe")  # Gruppe="3" in gesamtergebnis_01.xml
r.resolve("B90/GRÜNE")  # → the same Party
r.tagged("national_minority")  # → (SSW,) — the slot 4 exemption
```

Lookup normalises case and whitespace and nothing else. `GRUENE` and `GRÜNE` are two
aliases to be *recorded*, not one to be inferred; an unknown spelling raises rather
than guessing.

**The registry is one collection, not a snapshot of the current parliament.** It covers
every grouping that has held an elected Bundestag seat since 1949 — DP, KPD, WAV,
Zentrum, GB/BHE, DKP/DRP and the residual bucket "Andere Kreiswahlvorschläge" alongside
the parties of the 21st Bundestag. Party ids are minted **here and nowhere else**: if a
data bundle could mint its own `dp`, nothing would notice when two bundles disagreed,
whereas one collection lets the registry's validator see every id and alias at once.

## Non-negotiables

- **Everything is a frozen, validated pydantic model.** Invariants live on the type, so
  a bad number fails where it enters the system — when a reader parses a row out of a
  Landeswahlleiter file — not eight stages later as a seat count that is off by one.
  Unknown columns are a hard error (`extra="forbid"`); vote counts cannot be negative;
  a ballot section cannot let a voter pile five marks when they only have three.
  See [`model.py`](src/wahlwerk/model.py) and [`tests/test_validation.py`](tests/test_validation.py).
- **Exact arithmetic.** Divisor comparisons use `fractions.Fraction` or scaled integers,
  never floats. Float rounding both hides real ties and manufactures fake ones.
- **Ties are a result, not an error.** Where the law prescribes lots (Losentscheid), the
  engine returns an explicit [`Tie`](src/wahlwerk/ties.py) rather than letting sort order
  decide. `RecordedLot` replays a draw that actually happened.
- **One long table for all vote data.** A tally is a flat sequence of rows —
  `unit, section, party, candidate, count`. Cumulation is a bigger count; panachage is
  more rows; a new Land quirk is new rows, never new columns. That table is also
  literally one CSV file, which is what makes the archive format and the in-memory
  format the same thing.
- **Golden tests are the product.** Every historical election under every implemented law
  becomes a test asserting the official seat distribution exactly — party by party, Land
  list by Land list.
- **No bulk data in the repository.** Vote data lives in `wahlwerk-data`, which records
  each source's URL, retrieval date and SHA-256 so a bundle is reproducible without
  committing the multi-megabyte original. Fixtures committed here stay small and clearly
  sourced. What *is* shipped is reference data — the party registry, ~40 rows.

## Build order

Alongside the milestones, three things already work and are not milestones of their own:
the [party registry](#party-registry), the [archive reader](#loading-a-chamber-from-the-archive),
and `wahlwerk.examples` — each of which M1 needs before it can assert anything.

| | Milestone | Acceptance | |
|---|---|---|---|
| M0 | Interfaces only | Bayern and Hamburg expressible without changing a protocol | ✅ |
| M1 | BWahlG 2023 → Bundestag 2025 | exactly 630 seats, matching the Bundeswahlleiterin | |
| M2 | BWahlG 2013 → Bundestag 2021 | exactly 736 seats; law versioning becomes real | |
| M3 | BW LWG-2022 → Landtag 2026 | exact, **and** no special-casing in `apportionment/` | |
| M4 | Bayern | slots 1 and 3 break; the refactor is the deliverable | |
| M5 | One Kommunalwahlordnung with Kumulieren/Panaschieren | slot 2 becomes genuinely general | |
| M6 | Bundesrat as a derived body | Land election calendar, 69 votes, abstention modelled explicitly | |
| M7 | Metrics and sweep harness | Gallagher, ENP, Banzhaf, Shapley-Shubik; parameter sweeps | |

M0's acceptance criterion is executable: [`tests/test_m0_acceptance.py`](tests/test_m0_acceptance.py)
composes a Bayern-shaped and a Hamburg-shaped law out of stub slots, and both mypy and
pytest check that the protocols absorb them unchanged.

## Loading a chamber from the archive

```python
from wahlwerk import Chamber

chamber = Chamber.from_archive("de.bund.2025")
chamber.size  # 630
chamber.seats_by_party  # {'cdu': 164, 'afd': 152, 'spd': 120, ...}
chamber.mandates[0].unit  # 'de.bund.land.01' — the Land list the seat came from
```

One `Mandate` per seat, carrying its party and the unit whose list it came from. This is
the **declared** result — what the Bundeswahlleiterin published — which is exactly what
makes it usable as the target a derivation has to reproduce. `source` is
`MandateSource.UNRECORDED` and `person` is unset, because a published seat distribution
says nothing per seat.

The reader refuses rather than guessing: a bundle whose per-Land rows do not sum to its
national totals raises, as does one whose seat count contradicts its manifest, or whose
`schema` is a version this engine does not read. `Chamber.from_archive` works back to
1949 — `available()` lists what is present.

Requires the [archive](#repositories); `wahlwerk.io.find_archive` reports every path it
searched if none is found.

## Reference chambers

```bash
uv run python -m wahlwerk.examples.bundestag_2025
```

[`wahlwerk.examples.bundestag_2025`](src/wahlwerk/examples/bundestag_2025.py) builds the
21st Bundestag as a `Chamber` — 630 individual mandates from the published seat
distribution. Nothing is derived; it is the target the M1 golden test will be asserted
against. It shows why Fraktion and party cannot be collapsed (CDU and CSU are two parties
in one Fraktionsgemeinschaft of 208; the SSW's single member is fraktionslos because
Sec. 10 (1) GO-BT wants 32) and why the model records `MandateSource.UNRECORDED` rather
than inventing 630 plausible names.

It sits inside the package, not in a top-level `examples/`, so notebooks in
`wahlwerk-execute` can import it without `sys.path` surgery. The narrative version —
with the Sitzverteilung plotted one marker per `Mandate` — is
[`notebooks/bundestag_2025.ipynb`](https://github.com/js-chemE/wahlwerk-execute) over
there. A notebook can show a source of truth, never be one.

## Development

```bash
uv sync
uv run pytest        # tests
uv run mypy          # strict, src and tests
uv run ruff check .  # lint
uv run ruff format . # format
```

## Non-goals

- **Forecasting.** Predicting vote shares is a separate and much weaker discipline; the
  counterfactual engine needs none of it to be useful.
- **Simulating the Bundesverfassungsgericht.** Judicial review is modelled as a
  *constraint checker* over law configurations, never as an agent.
- **Voter behaviour models.** Votes are inputs, historical or sampled.

## Data and attribution

No election data is committed here. The party registry under
[`src/wahlwerk/data/`](src/wahlwerk/data/) is reference data, seeded from the
Bundeswahlleiterin's BTW 2025 open data.

Results are generally published under Datenlizenz Deutschland (dl-de/by-2-0), which
requires attribution. Every bundle in `wahlwerk-data` carries its publisher, title, URL,
licence and attribution in `election.toml`, and `Bundle.source` keeps them — so the
attribution travels with anything republished from it rather than being left behind at the
read. Planned sources: `bundeswahlleiterin.de`, the sixteen Landeswahlleiter,
`dip.bundestag.de`, and `wahlrecht.de` as an independent check on the allocation
algorithms.

## Licence

Apache-2.0. See [LICENSE](LICENSE) and [CITATION.cff](CITATION.cff).
The API stays on `0.x` until the six-slot interface has survived contact with Bayern.
