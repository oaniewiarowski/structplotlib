"""
structplotlib.reduce.frame_stations
==================================

Pure dataframe logic: filtering, enveloping, and reduction to plot-ready data.

Key contract:
- Input dataframes are expected to already be normalized to canonical columns
  (see structplotlib.schema.normalize_df / load_df).
- This module contains *no plotting*.

Important behaviors (strict-by-default):
- Duplicates at the same (story, member_id, station, output_case, case_type, step_type)
  are aggregated (default: max) **only when they refer to the same physical segment**.
  If an ``element`` column is present (CSI element breakdown exports), duplicates at the
  same station across *different* elements are preserved (left/right values at element
  boundaries can differ and are meaningful).
- reduce_plan() will FAIL LOUDLY if multiple (output_case, case_type, step_type) triples
  remain per (story, member_id). Filter/envelope first.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

from ..schema.base import require_columns

Agg = Literal["max", "mean", "min"]
Mode = Literal["max", "min", "absmax"]


def filter_cases(df: pd.DataFrame, cases: list[str] | None) -> pd.DataFrame:
    """Filter to the exact output_case names in `cases`.

    Parameters
    ----------
    df:
        Canonical dataframe with an ``output_case`` column.
    cases:
        List of output_case names to keep. If None, returns df unchanged.

    Raises
    ------
    KeyError (SchemaError subclass) if required columns are missing.
    ValueError if `cases` includes names not present in df.
    """
    require_columns(df, ["output_case"], where="filter_cases")
    if cases is None:
        return df
    cases = list(cases)
    available = set(pd.unique(df["output_case"]))
    missing = [c for c in cases if c not in available]
    if missing:
        raise ValueError(
            "[filter_cases] Requested output_case values not found: "
            + repr(missing)
            + ". Available: "
            + repr(sorted(available)[:30])
            + (" ..." if len(available) > 30 else "")
        )
    return df[df["output_case"].isin(cases)].copy()


def envelope_by_member(
    df: pd.DataFrame,
    *,
    value_col: str = "dcr_max",
    mode: Mode = "absmax",
    station_agg: Agg = "max",
) -> pd.DataFrame:
    """Select the governing (output_case, case_type, step_type) triple per member.

    The governing triple is chosen by scanning stations within each triple, after
    aggregating duplicates at the station level.

    If an ``element`` column is present, station-level aggregation is performed within
    (story, member_id, element, station, case triple), so duplicate stations at element
    boundaries are preserved for envelope scoring.

    - mode="max": pick triple whose station-maximum is largest
    - mode="min": pick triple whose station-minimum is smallest
    - mode="absmax": pick triple whose max(abs(value)) is largest

    Returns *all rows* from the governing triple for each (story, member_id).

    Notes
    -----
    This function does not aggregate stations in the returned dataframe. Use reduce_plan()
    afterwards to produce plot-ready station rows.
    """
    require_columns(
        df,
        [
            "story",
            "member_id",
            "station",
            "output_case",
            "case_type",
            "step_type",
            value_col,
        ],
        where="envelope_by_member",
    )

    if station_agg not in ("max", "min", "mean"):
        raise ValueError(
            f"[envelope_by_member] station_agg must be one of 'max','min','mean', got {station_agg!r}"
        )
    if mode not in ("max", "min", "absmax"):
        raise ValueError(
            f"[envelope_by_member] mode must be one of 'max','min','absmax', got {mode!r}"
        )

    # 1) Aggregate duplicates at the station level *within* each case triple
    gkeys = ["story", "member_id", "output_case", "case_type", "step_type", "station"]
    if "element" in df.columns:
        gkeys.append("element")
    station = df.groupby(gkeys, sort=False, as_index=False).agg(v=(value_col, station_agg))

    # 2) Score each triple for each member
    tkeys = ["story", "member_id", "output_case", "case_type", "step_type"]
    if mode == "max":
        scores = station.groupby(tkeys, sort=False, as_index=False).agg(score=("v", "max"))
        ascending = False
    elif mode == "min":
        scores = station.groupby(tkeys, sort=False, as_index=False).agg(score=("v", "min"))
        ascending = True
    else:  # absmax
        station = station.assign(abs_v=station["v"].abs())
        scores = station.groupby(tkeys, sort=False, as_index=False).agg(score=("abs_v", "max"))
        ascending = False

    # Stable tie-breaking: mergesort keeps input order stable.
    scores = scores.sort_values(
        ["story", "member_id", "score"], ascending=[True, True, ascending], kind="mergesort"
    )
    ctrl = scores.groupby(["story", "member_id"], sort=False, as_index=False).first()[
        ["story", "member_id", "output_case", "case_type", "step_type"]
    ]

    out = df.merge(
        ctrl, on=["story", "member_id", "output_case", "case_type", "step_type"], how="inner"
    )
    sort_cols = ["story", "member_id", "station"]
    if "element" in out.columns:
        sort_cols.append("element")
    out = out.sort_values(sort_cols, kind="mergesort")
    return out.reset_index(drop=True)


def _assert_single_case_triple_per_member(df: pd.DataFrame) -> None:
    """Fail loudly if multiple case triples remain per (story, member_id)."""
    require_columns(
        df,
        ["story", "member_id", "output_case", "case_type", "step_type"],
        where="reduce_plan",
    )
    triples = df[["story", "member_id", "output_case", "case_type", "step_type"]].drop_duplicates()
    counts = triples.groupby(["story", "member_id"], sort=False).size()
    bad = counts[counts > 1]
    if not bad.empty:
        # show up to a few offenders
        offenders = list(bad.index[:8])
        raise ValueError(
            "[reduce_plan] Multiple (output_case, case_type, step_type) triples remain for some members. "
            "Filter to a single case, select a single step_type, or call envelope_by_member() first. "
            f"Examples (story, member_id) with >1 triple: {offenders}"
        )


def reduce_plan(
    df: pd.DataFrame,
    *,
    value_col: str = "dcr_max",
    station_agg: Agg = "max",
) -> pd.DataFrame:
    """Reduce canonical station-level data to plot-ready rows.

    Output columns:
        story, member_id, station, output_case, value, x_i,y_i,x_j,y_j, x,y
        (and ``element`` / ``elem_station`` if present in the input)

    This:
    - aggregates duplicates per (member_id, station) using station_agg (default max)
      If an ``element`` column is present, duplicates are aggregated per (element, station)
      instead, preserving left/right values at element boundaries.
    - asserts each member_id has a single (output_case, case_type, step_type) triple
    - computes centerpoint x,y

    Raises
    ------
    ValueError if multiple case triples remain or if member geometry is inconsistent.
    """
    require_columns(
        df,
        ["story", "member_id", "station", "x_i", "y_i", "x_j", "y_j", value_col],
        where="reduce_plan",
    )

    _assert_single_case_triple_per_member(df)

    if station_agg not in ("max", "min", "mean"):
        raise ValueError(
            f"[reduce_plan] station_agg must be one of 'max','min','mean', got {station_agg!r}"
        )

    # Geometry consistency: endpoints should not vary within a member
    geom = df.groupby(["story", "member_id"], sort=False)[["x_i", "y_i", "x_j", "y_j"]].nunique(
        dropna=False
    )
    bad_geom = geom[(geom > 1).any(axis=1)]
    if not bad_geom.empty:
        offenders = list(bad_geom.index[:8])
        raise ValueError(
            "[reduce_plan] Inconsistent geometry within some members (endpoints vary across rows). "
            f"Examples (story, member_id): {offenders}"
        )

    gkeys = ["story", "member_id", "station"]
    if "element" in df.columns:
        gkeys.append("element")

    agg_kwargs = dict(
        value=(value_col, station_agg),
        output_case=("output_case", "first"),
        x_i=("x_i", "first"),
        y_i=("y_i", "first"),
        x_j=("x_j", "first"),
        y_j=("y_j", "first"),
    )
    if "elem_station" in df.columns:
        # Local station measured along the finite element (resets to 0 at each element).
        # Useful for debugging and for downstream logic that needs element-local context.
        agg_kwargs["elem_station"] = ("elem_station", "first")

    reduced = df.groupby(gkeys, sort=False, as_index=False).agg(**agg_kwargs)

    reduced["x"] = 0.5 * (reduced["x_i"] + reduced["x_j"])
    reduced["y"] = 0.5 * (reduced["y_i"] + reduced["y_j"])
    return reduced
