"""
structplotlib.styles.norms
==========================

Normalization helpers for value ranges (vmin/vmax, abs norms).

This module provides utilities for computing normalization bounds from data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def infer_norm_bounds(
    values: pd.Series | np.ndarray,
    *,
    norm_min: float | None = None,
    norm_max: float | None = None,
    use_abs: bool = False,
) -> tuple[float, float]:
    """Infer normalization bounds from a value array.

    Parameters
    ----------
    values:
        Array or Series of values to normalize.
    norm_min:
        If provided, use this as the lower bound.
    norm_max:
        If provided, use this as the upper bound.
    use_abs:
        If True, compute bounds from absolute values.

    Returns
    -------
    (vmin, vmax) tuple for use with matplotlib colormaps.
    """
    if isinstance(values, pd.Series):
        vals = values.to_numpy(float)
    else:
        vals = np.asarray(values, dtype=float)

    if use_abs:
        vals = np.abs(vals)

    if norm_min is None:
        vmin = float(np.min(vals))
    else:
        vmin = float(norm_min)

    if norm_max is None:
        vmax = float(np.max(vals))
    else:
        vmax = float(norm_max)

    return (vmin, vmax)
