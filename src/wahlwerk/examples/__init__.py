"""Reference chambers, importable so that analyses outside this repo can use them.

These live *inside* the package rather than in a top-level ``examples/`` directory for
one reason: `wahlwerk-execute` holds the notebooks, and a notebook in another repository
cannot import from a directory that is not installed. Shipping the module costs a few
hundred bytes and removes the need for any ``sys.path`` surgery.

Each module here is a chamber typed in from a published result -- nothing is derived.
They are the targets the golden tests will be asserted against. Once `wahlwerk-data`
carries the corresponding bundles, ``io.read_bundle("de.bund.2025").declared`` supersedes
them and they can go.
"""

from __future__ import annotations

__all__: list[str] = []
