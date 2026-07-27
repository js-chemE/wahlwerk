"""Small reference tables shipped with the package.

Reference data is not election data. What lives here is the handful of tables that are
tiny, slow-changing, and needed before any source file can even be parsed -- currently
the party registry. Vote counts and results are never shipped: they are fetched (see
``scripts/fetch_data.py``) or kept as clearly sourced fixtures under ``tests/golden/``.

Files are CSV for the same reason the vote tally is: diffable, editable without a
Python session, and readable by anything.
"""

from __future__ import annotations

__all__: list[str] = []
