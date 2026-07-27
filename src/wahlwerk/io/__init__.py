"""Reading and writing election data.

Everything that touches a file lives here, so the model and the six slots never do. The
archive itself is a separate repository (`wahlwerk-data`); the engine reads it and never
depends on it.
"""

from __future__ import annotations

from wahlwerk.io.archive import (
    ARCHIVE_ENV,
    SCHEMA_SUPPORTED,
    ArchiveNotFound,
    Bundle,
    DeclaredSeats,
    available,
    bundle_path,
    find_archive,
    load_chamber,
    read_bundle,
)

__all__ = [
    "ARCHIVE_ENV",
    "SCHEMA_SUPPORTED",
    "ArchiveNotFound",
    "Bundle",
    "DeclaredSeats",
    "available",
    "bundle_path",
    "find_archive",
    "load_chamber",
    "read_bundle",
]
