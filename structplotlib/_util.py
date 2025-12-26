"""
structplotlib._util
==================

Small shared helper functions used across the package.
"""
from __future__ import annotations

import re
from typing import Sequence


def _norm_col(s: str) -> str:
    """Normalize a column name to compare potential aliases (spaces/underscores/case ignored)."""
    return re.sub(r"[\s_]+", "", str(s)).lower()


def _did_you_mean(available: Sequence[str], expected: str) -> list[str]:
    """Return candidate column names that match expected after normalization."""
    ek = _norm_col(expected)
    hits = [c for c in available if _norm_col(c) == ek]
    return hits

