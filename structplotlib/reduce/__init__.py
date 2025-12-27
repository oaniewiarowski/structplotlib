"""
structplotlib.reduce
===================

Data reduction and envelope selection for plotting.

- frame_stations: Station-level aggregation and envelope selection
"""
from .frame_stations import (
    Agg,
    Mode,
    envelope_by_member,
    filter_cases,
    reduce_plan,
)

__all__ = [
    "filter_cases",
    "envelope_by_member",
    "reduce_plan",
    "Agg",
    "Mode",
]
