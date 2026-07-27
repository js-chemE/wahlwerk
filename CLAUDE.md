# wahlwerk

German electoral and parliamentary systems as rules-as-code: a deterministic engine
parameterised by an electoral law, so small changes to the law can be evaluated against
real historical votes. Bundestag, Landtage, kommunale Vertretungen, plus the Bundesrat
as a derived body.

**Status: M0 — interfaces only.** Protocols, models and event types exist, plus three
things that are not milestones but that M1 needs: the party registry (`registry.py`), the
archive reader (`io/`), and reference chambers (`examples/`).

**There is no law implementation.** Nothing is *derived*: `Chamber.from_archive(...)`
reads a published result, it does not compute one. Event `apply` methods raise
`NotImplementedError` naming the milestone they land in; that is deliberate, not an
oversight. Do not implement one slot ahead of its milestone to make a demo work.

## Commands

```bash
uv sync
uv run pytest -q                   # tests
uv run mypy                        # strict; src and tests
uv run ruff check . && uv run ruff format .
uv run python -m wahlwerk.examples.bundestag_2025
```

All four must pass before anything is called done. mypy has no `python_version` pin —
the CI matrix runs it on 3.11, 3.12 and 3.13, which checks compatibility for real.

The engine has **no** jupyter or matplotlib dependency and must not grow one; notebooks
live in wahlwerk-execute.

## Language policy

English is the language of code; German electoral law is the subject matter.

> **Translate the concept. Keep the term of art.**

A term is *of art* if translating it would lose a distinction the law makes, or if you
would have to invent the English.

- **Keep German**: `Zweitstimme`, `Wahlkreis`/`Stimmkreis`/`Wahlbezirk` (English has one
  word for three legally distinct things), `Überhang`, `Ausgleich`,
  `Grundmandatsklausel`, `Zweitstimmendeckung`, `Fraktion`, `Nachrücken`,
  `Wahlprüfung`, `Auflösung`, `Landesliste`, `Losentscheid`, `Kumulieren`,
  `Panaschieren`.
- **Use English**: `party`, `seat`, `unit`, `level`, `count`, `share`, `threshold`,
  `winner`, `allocation` — the same concept in every country.
- The test: **does an official source use this word?** If the Bundeswahlleiterin, a
  statute or the BVerfG says it, keep it. If you reached for a dictionary, you are
  inventing vocabulary nobody uses.

**Orthography.** Identifiers and filenames are ASCII-transliterated (`ue`, `oe`, `ae`,
`ss`): `Aufloesung`, `wahlpruefung.py`, `MandateSource.UEBERHANG`, party id `gruene`.
Prose, data and user-facing output use correct German: `Auflösung`, `Wahlprüfung`,
`Überhang`, `BÜNDNIS 90/DIE GRÜNEN`. So a class docstring reads

```python
class Aufloesung(Model):
    """Auflösung under Art. 68 GG: the term ends early."""
```

Sphinx roles name the identifier — ``:class:`Aufloesung` `` stays ASCII. Never put an
umlaut in `__all__` or an import; ruff `F822` catches it, but do not rely on that.

**Everything else is English**: docstrings, comments, test names, commit messages,
error messages, docs.

**Legal citations** keep the German short form and always carry the section:
`Art. 68 GG`, `Sec. 10 (1) GO-BT`, `Sec. 4 (2) BWahlG`. Judgments carry their docket:
`BVerfG, 2 BvF 1/23`. Cite the provision a rule implements in the docstring of the code
that implements it.

## Identifiers

Every stable key is a lowercase ASCII dotted path, narrowest scope last. The scheme is
defined and **enforced** in `ids.py`: each id is a `NewType` over a pattern-constrained
`Annotated[str, StringConstraints(...)]`, so `"de.bund.Bundestag"` fails validation
where it is constructed, and mypy still refuses to pass a `PartyId` where a `UnitId`
belongs.

```
BodyId       de.bund.bundestag   de.by.landtag        DottedKey
LawId        de.bund.bwahlg.2023 …+apportionment      DottedKey + "+slot" suffixes
UnitId       de.bund.land.01     de.bund.wk.001       DottedKey
PartyId      cdu   gruene   team-todenhoefer          DottedKey
CandidateId  ...                                      DottedKey
LevelName    wahlkreis   land   bund                  Slug (single segment)
SectionName  erststimme   zweitstimme                 Slug
Fraktion.id  cdu-csu   spd                            Slug
```

**Add a new id type in `ids.py`, never as a bare `str` on a model.** `body` was `str`
in five places before it became `BodyId`; that is the failure mode. Free-form text —
`name`, `notes`, `citation`, `docket`, `Mandate.seat`, provenance strings — stays `str`
deliberately.

A `BodyId` names an institution and is only a key. The institution *model* (name,
jurisdiction, Bundesrat vote weight, election calendar) arrives with M6.

## Fields and validation

`model.py` sets `use_attribute_docstrings=True`, so the docstring under a field becomes
its schema description. That is the documented way to describe a field.

```python
class Term(Model):
    body: BodyId
    """The institution this term is a Wahlperiode of, e.g. ``de.bund.bundestag``."""

    scheduled_end: date | None = None
```

Rules, in order of preference:

1. **Reach for a shared alias before `Field`.** `model.py` exports `Count` (≥ 0),
   `Seats` (≥ 0) and `Share` (exact `Fraction`, 0–1); `ids.py` exports `Slug`,
   `DottedKey`, `LawId`. If the same constraint appears three times, it wants an alias,
   not three `Field(ge=0)`.
2. **Use `Field` only for a constraint the type cannot carry**: `ge`, `gt`,
   `min_length`, `pattern`, `discriminator`. `votes_per_voter: int = Field(default=1, ge=1)`
   is right; the constraint is local and does not recur.
3. **Do not use `Field` for plain defaults.** Write `= 0`, `= ()`, `= {}`. Pydantic
   copies mutable defaults, so `default_factory` is noise — which is why ruff's RUF012
   is disabled here.
4. **Never `Field(description=...)`** — use the attribute docstring (see above).
5. **Never `Field(alias=...)` on a domain model.** Source column names (`Gruppe`,
   `Anzahl`, `Stimmart`) are mapped in the reader in `io/`, not smuggled into the model.
   Otherwise the domain vocabulary silently becomes whichever Landeswahlleiter was
   parsed first.
6. **Cross-field rules go in `@model_validator(mode="after")`**, returning `self`, with
   a message that names the offending values: `f"cap {self.cap} is below minimum
   {self.minimum}"`. Not `f"invalid SeatTargets"`.
7. **Prefer a validator over a comment.** If a docstring says "must be", make it must be.

## Architecture

Every electoral law decomposes into six orthogonal slots. That decomposition **is** the
modularity of the package; a concrete law composes six implementations plus validity
dates, and a reform proposal is that object with one slot replaced
(`ElectoralLaw.variant`).

| # | Module | Slot |
|---|---|---|
| 1 | `tiers.py` | how territory maps to allocation units, and how they nest |
| 2 | `ballots.py` | how many votes a voter casts and what they attach to |
| 3 | `aggregation.py` | which votes feed the proportional entitlement |
| 4 | `eligibility.py` | threshold, the tier it is computed at, exemptions |
| 5 | `apportionment/` | divisor and quota methods, and tier resolution order |
| 6 | `assignment.py` | who occupies the seats; district winners reconciled |

`io/` is where anything touching a file lives, so the model and the six slots never do.

The pipeline order is fixed in `events/election.py`: ballot → aggregate →
resolve districts → eligibility → apportion → assign. Steps 3 and 6 are the same slot,
split because eligibility sits between them (the Grundmandatsklausel needs district
wins). That is the only ordering constraint the decomposition imposes.

Events, not elections, are the spine: `State --(Event)--> State`. Elections are one
event type. `BodyState.origin` keeps the whole `ElectionResult` including inputs, which
is what makes `Wahlprüfung` a re-derivation rather than surgery on a finished chamber.

## Hard rules

- **`apportionment/` contains zero German content.** Opaque keys, integer votes, a seat
  total. If a Land quirk appears there, refactor immediately — do not special-case.
- **Exact arithmetic.** `fractions.Fraction` or scaled integers. Never `float`. Float
  rounding both hides real ties and manufactures fake ones, and the symptom is a seat
  count off by one that costs days.
- **Ties are a result, not an error.** Return `Tie`; never let sort order decide. The
  default `TieBreaker` refuses. `RecordedLot` replays a Losentscheid that happened;
  `Deterministic` is for sweeps only and never for a golden test.
- **Every data type is a frozen pydantic model** (`model.py`: `frozen`, `extra="forbid"`,
  `validate_default`). Put invariants on the type so bad data fails where it enters, not
  eight stages downstream. Prefer `tuple`/`frozenset` over `list`/`set` in fields.
- **The six slots stay `runtime_checkable` Protocols**, never base classes.
- **Vote data is one long table**: rows of `unit, section, party, candidate, count`. A
  new Land quirk is new rows, never new columns. Cumulation is a bigger count;
  panachage is more rows.
- **Record absence, never invent it.** `MandateSource.UNRECORDED` and optional
  `person`/`unit`/`level` exist so a chamber known only from a published seat
  distribution says so. Never fabricate plausible names, and never accept `UNRECORDED`
  in a golden test.
- **No fuzzy party matching.** `registry.resolve` normalises case and whitespace and
  nothing else; an unknown spelling raises and is a question for a human.
- **No bulk data in the repo.** Vote data lives in `wahlwerk-data`. `tests/golden/` will
  hold small, clearly sourced fixtures from M1 on; `/data/` is gitignored for anything
  fetched. Every source needs its dl-de/by-2-0 attribution recorded and carried through
  the read — `Bundle.source` exists so it is not left behind.
- **Golden tests never skip and never xfail.** They are the product.

## Layout

```
src/wahlwerk/
  model.py            pydantic base: Model, SlotModel, Count, Seats, Share
  ids.py              PartyId/CandidateId/UnitId, Party, Candidacy, Nominations
  ties.py             Tie, TieBreaker, RecordedLot
  mandate.py          Mandate, MandateSource  (top-level: both slot 6 and state need it)
  tiers.py ballots.py aggregation.py eligibility.py assignment.py     slots 1-4, 6
  apportionment/      slot 5 — base.py, tiered.py
  law.py              ElectoralLaw, LawRegistry
  registry.py         PartyRegistry, german_parties() — the one place ids are minted
  data/               shipped reference CSVs (parties, aliases) — never vote data
  state/              chamber.py, government.py
  events/             base.py, results.py, election.py, nachruecken.py,
                      wahlpruefung.py, aufloesung.py
  io/                 archive.py — reads wahlwerk-data bundles; the only file access
  examples/           reference chambers, in the package so notebooks elsewhere import them
tests/golden/         official results as fixtures (none yet — M1)
```

`io/` is the only place that touches a file. `examples/` is inside the package on purpose:
`wahlwerk-execute` holds the notebooks, and a notebook in another repository cannot import
from a top-level directory that is not installed.

## Build order

M0 interfaces ✅ · M1 BWahlG-2023 → BTW 2025 (exactly 630) · M2 BWahlG-2013 → BTW 2021
(736) · M3 BW LWG-2022 · M4 Bayern (breaks slots 1 and 3 — the refactor is the
deliverable) · M5 Kommunalwahl with Kumulieren/Panaschieren (breaks slot 2) ·
M6 Bundesrat (abstention counts against the 35-vote threshold — model it explicitly) ·
M7 metrics and sweeps.

Do not proceed past a milestone whose acceptance criterion is unmet.

## Sibling repositories

Three repos, cloned side by side:

```
CODE/
  wahlwerk/          the engine       Apache-2.0     ← you are here
  wahlwerk-data/     the archive      dl-de/by-2-0
  wahlwerk-execute/  notebooks        depends on both
```

- **wahlwerk never depends on wahlwerk-data.** From M1 the golden fixtures live here under
  `tests/golden/`, small and gzipped, so CI runs offline. The archive — every election
  since 1949, sixteen Länder, kommunal — lives in `wahlwerk-data`, which is cloned, not
  vendored.
- **Resolution order**: `$WAHLWERK_DATA` → `../wahlwerk-data` → `~/.cache/wahlwerk/data`,
  in `io/archive.py`. The sibling clone is the zero-config path, never a requirement; the
  test suite must pass with the archive absent, so anything touching it builds a synthetic
  bundle in `tmp_path`. The real archive is exercised in wahlwerk-data's own tests.
- **An election id maps to a path by its last dot**: `de.bund.2025` →
  `elections/de.bund/2025`, `de.nw.koeln.2025` → `elections/de.nw.koeln/2025`. Both repos
  define this; it is the one thing they must agree on.
- **`Chamber.from_archive(id)`** is the entry point. It imports `io` inside the method so
  `state` never depends on `io` at module level.
- **Bundles carry `schema = N`** in `election.toml`; the engine declares the range it
  reads (`SCHEMA_SUPPORTED`). A format change must be a loud break, never a silent
  mis-parse — and a bundle that fails its own internal cross-checks (per-unit rows not
  summing to the national ones, a seat count contradicting the manifest) raises rather
  than producing a chamber that is quietly the wrong size.
- **Notebooks live in wahlwerk-execute, not here.** It depends on wahlwerk through an
  editable path dependency (`[tool.uv.sources]`), so anything a notebook imports must be
  inside the installed package — hence `wahlwerk.examples`, not a top-level `examples/`.
  wahlwerk itself has no jupyter or matplotlib dependency and must not grow one.

## Notebooks (in wahlwerk-execute)

- **A notebook can show a source of truth, never be one.** Logic and data live in a
  module under `wahlwerk/examples/` that the tests import; the `.ipynb` imports it and
  adds the narrative. Never duplicate a seat distribution into both — they drift.
- **Commit executed notebooks.** Outputs are the point of an example; re-execute with
  `uv run jupyter nbconvert --to notebook --execute --inplace <nb>` after changing the
  module it imports.
- **Party colours are presentation, not domain.** They live in the notebook, never in
  `parties_de.csv` or `Party.tags` — `tags` is for properties the *law* reasons over.
  The conventional German palette fails a CVD audit (SPD red beside Grüne green is
  ΔE 3.9 for deutan, and no reordering fixes it because that adjacency is the seating
  order). Keep the convention — a reader identifies the SPD by red — and discharge it
  with secondary encoding: direct labels on every block, seat counts in the legend, and
  the table view above the chart. Never colour alone.
- **Text wears text tokens**, never the series colour.

## Working style here

- The design brief (`wahlwerk-design-brief.md`, supplied by the author) is the spec.
  Deviate where there is a better answer, but say so rather than drifting silently.
- Docstrings explain *why the law is like this*, not what the code does. That context is
  the expensive part and it is what a reader six months later needs.
- Prefer adding a validator over adding a comment.
