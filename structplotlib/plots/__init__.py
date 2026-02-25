"""
structplotlib.plots
==================

Matplotlib plotting utilities.

- plan_axes: Axes-level composable helpers (lines/fill/labels/colorbar)
- plan: Seaborn-esque high-level wrappers built on composable primitives
"""

from .plan import planplot
from .plan_axes import (
    plan_annotate,
    plan_colorbar,
    plan_fill,
    plan_lines,
    plan_point_labels,
    plan_points,
    plan_show_values,
)

__all__ = [
    "planplot",
    "plan_lines",
    "plan_fill",
    "plan_annotate",
    "plan_points",
    "plan_point_labels",
    "plan_show_values",
    "plan_colorbar",
]
