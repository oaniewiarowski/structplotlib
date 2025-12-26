"""
structplotlib.reduce
===================

Data reduction and envelope selection for plotting.

- frame_stations: Station-level aggregation and envelope selection
"""
from .frame_stations import (
    filter_cases,
    envelope_by_member,
    reduce_plan,
    Agg,
    Mode,
)

__all__ = [
    "filter_cases",
    "envelope_by_member",
    "reduce_plan",
    "Agg",
    "Mode",
]

