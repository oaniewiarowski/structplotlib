"""
structplotlib

Strict, small plotting utilities for station-level post-processed CSI (ETABS/SAP2000) frame data.
"""
from .schema.csi import load_df, normalize_df, Source, Table
from .schema.base import SchemaError
from .reduce.frame_stations import filter_cases, envelope_by_member, reduce_plan, Agg, Mode
from .plots.plan_fill import plot_plan, plot_plan_by_story, plot_fill_plan

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
]
