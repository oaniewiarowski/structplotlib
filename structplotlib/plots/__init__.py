"""
structplotlib.plots
==================

Matplotlib plotting utilities.

- plan_fill: Plan view fill diagrams with station-level coloring
- plan: Seaborn-esque high-level wrappers built on composable primitives
"""

# NOTE: Legacy API (`plot_plan`, `plot_plan_by_story`, `plot_fill_plan`) is deprecated.
# It remains available temporarily for compatibility but will be removed soon.

from .plan import planplot
from .plan_axes import plan_annotate, plan_colorbar, plan_fill, plan_lines, plan_show_values
from .plan_fill import (
    plot_fill_plan,
    plot_plan,
    plot_plan_by_story,
)

__all__ = [
    "plot_plan",
    "plot_plan_by_story",
    "plot_fill_plan",
    "planplot",
    "plan_lines",
    "plan_fill",
    "plan_annotate",
    "plan_show_values",
    "plan_colorbar",
]
