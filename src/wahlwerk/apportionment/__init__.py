"""Slot 5 -- apportionment. Pure math, zero German content.

base.py     the single-pot method interface
tiered.py   linked multi-tier allocation
divisor.py  Sainte-Lague/Schepers, D'Hondt, Adams, Huntington-Hill  (M1)
quota.py    Hare-Niemeyer and friends                               (M1)
"""

from __future__ import annotations

from wahlwerk.apportionment.base import (
    Allocation,
    ApportionmentMethod,
    Key,
    SeatConstraints,
)
from wahlwerk.apportionment.tiered import Entitlement, SeatTargets, TieredApportionment

__all__ = [
    "Allocation",
    "ApportionmentMethod",
    "Entitlement",
    "Key",
    "SeatConstraints",
    "SeatTargets",
    "TieredApportionment",
]
