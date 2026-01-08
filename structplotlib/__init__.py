"""
structplotlib

Strict, small plotting utilities for station-level post-processed CSI (ETABS/SAP2000) frame data.
"""

# NOTE: Legacy plotting API (`plot_plan`, `plot_plan_by_story`, `plot_fill_plan`) is deprecated.
# It remains available temporarily for compatibility but will be removed soon.

from .plots.plan import planplot
from .plots.plan_axes import (
    plan_annotate,
    plan_colorbar,
    plan_fill,
    plan_lines,
    plan_show_values,
)
from .plots.plan_fill import plot_fill_plan, plot_plan, plot_plan_by_story
from .reduce.frame_stations import (
    Agg,
    Mode,
    envelope_by_member,
    filter_cases,
    reduce_plan,
)
from .schema.base import SchemaError
from .schema.csi import Source, Table, load_df, normalize_df

__all__ = [
    # Schema
    "load_df",
    "normalize_df",
    "SchemaError",
    "Source",
    "Table",
    # Reduction
    "filter_cases",
    "envelope_by_member",
    "reduce_plan",
    "Agg",
    "Mode",
    # Plotting
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
