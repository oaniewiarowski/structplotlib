"""
structplotlib

Strict, small plotting utilities for station-level post-processed CSI (ETABS/SAP2000) frame data.
"""

from .plots.plan import planplot
from .plots.plan_axes import (
    plan_annotate,
    plan_colorbar,
    plan_fill,
    plan_lines,
    plan_show_values,
)
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
    "planplot",
    "plan_lines",
    "plan_fill",
    "plan_annotate",
    "plan_show_values",
    "plan_colorbar",
]
