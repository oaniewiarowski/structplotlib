"""
structplotlib.plots.plan_axes
=============================

Axes-level (Matplotlib-composable) helpers for plan plotting.

These functions are designed to behave like Matplotlib / seaborn axes-level functions:
- They draw onto a single `matplotlib.axes.Axes` (use `ax=` or default to current axes).
- They do *not* own the figure and do not do faceting.
- They do not perform business logic like case filtering/enveloping/reduction/normalization.
  (Do that upstream with `normalize_df`, `filter_cases`, `envelope_by_member`, `reduce_plan`,
   or with a higher-level wrapper like `planplot`.)
- They return Matplotlib artists for post-hoc customization and for testing.

Input contracts
---------------
`plan_fill` / `plan_show_values` assume station-level numeric data with:
- geometry endpoints: x_i,y_i,x_j,y_j
- identity grouping: member_id (or your chosen `member=` column)
- station distance from I-end: station (global station, length units)
- numeric values: `value` (column name)

`plan_lines` assumes one row per member (or will draw one segment per member using the first row).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .plan_fill_primitives import (
    add_colorbar as _add_colorbar,
    annotate_frames as _annotate_frames,
    frames_station_xy,
    plot_frames_fill,
    plot_frames_lines,
    select_controlling_stations,
)


def plan_lines(
    data: pd.DataFrame,
    *,
    ax=None,
    member: str | None = "member_id",
    x_i: str = "x_i",
    y_i: str = "y_i",
    x_j: str = "x_j",
    y_j: str = "y_j",
    story: str | None = None,
    story_value: str | None = None,
    **line_kws,
):
    """Draw member centerlines as straight segments (axes-level).

    Parameters
    ----------
    data:
        Dataframe with endpoints. If `member` is provided, draws one segment per member
        (using the first row per member).
    ax:
        Axes to draw on. If None, uses `plt.gca()`.
    **line_kws:
        Passed through to `ax.plot(...)` (e.g. color, linewidth, alpha, zorder).

    Returns
    -------
    lines:
        list[matplotlib.lines.Line2D]
    """
    if ax is None:
        ax = plt.gca()
    out = plot_frames_lines(
        data=data,
        ax=ax,
        x_i=x_i,
        y_i=y_i,
        x_j=x_j,
        y_j=y_j,
        member=member,
        story=story,
        story_value=story_value,
        line_kws=dict(line_kws),
    )
    return out["lines"]


def plan_fill(
    data: pd.DataFrame,
    *,
    ax=None,
    value: str = "value",
    member: str = "member_id",
    station: str = "station",
    x_i: str = "x_i",
    y_i: str = "y_i",
    x_j: str = "x_j",
    y_j: str = "y_j",
    densify: Literal["none", "linear"] = "linear",
    k_per_segment: int = 5,
    cmap: str = "turbo",
    norm=None,
    vmin: float | None = None,
    vmax: float | None = None,
    marker: str = "s",
    s: float = 36.0,
    alpha: float = 0.95,
    linewidths: float = 0.0,
    zorder: float = 3.0,
    **scatter_kws,
):
    """Draw numeric station results as colored markers along members (axes-level).

    This is the “fill” renderer. It returns the PathCollection so callers can attach colorbars
    or tweak normalization.

    Parameters
    ----------
    data:
        Station-level numeric dataframe (already filtered/reduced upstream).
    value:
        Column name for numeric values to colormap.
    densify, k_per_segment:
        Densification between stations (visual-only interpolation).
    **scatter_kws:
        Passed through to `ax.scatter(...)` via `plot_frames_fill(...)`.

    Returns
    -------
    markers:
        matplotlib.collections.PathCollection
    """
    if ax is None:
        ax = plt.gca()
    out = plot_frames_fill(
        data=data,
        ax=ax,
        x_i=x_i,
        y_i=y_i,
        x_j=x_j,
        y_j=y_j,
        member=member,
        station=station,
        value=value,
        densify=densify,
        k_per_segment=k_per_segment,
        cmap=cmap,
        norm=norm,
        vmin=vmin,
        vmax=vmax,
        scatter_kws={
            "marker": marker,
            "s": float(s),
            "alpha": float(alpha),
            "linewidths": float(linewidths),
            "zorder": float(zorder),
            **dict(scatter_kws),
        },
    )
    return out["markers"]


def plan_annotate(
    data: pd.DataFrame,
    *,
    ax=None,
    text: str | Callable[[pd.Series], str] = "member_id",
    where: Literal["midpoint", "i_end", "j_end", "xy"] = "midpoint",
    rotate_with_member: bool = True,
    normal_offset: float = 0.0,
    mask: Sequence[bool] | None = None,
    # geometry / xy
    x: str | None = None,
    y: str | None = None,
    x_i: str = "x_i",
    y_i: str = "y_i",
    x_j: str = "x_j",
    y_j: str = "y_j",
    **text_kws,
):
    """Annotate members/rows with text labels (axes-level).

    This is a thin wrapper over the primitive `annotate_frames`, with `**text_kws`
    passed through to `ax.text(...)`.

    Returns
    -------
    texts:
        list[matplotlib.text.Text]
    """
    if ax is None:
        ax = plt.gca()
    out = _annotate_frames(
        data=data,
        ax=ax,
        x=x,
        y=y,
        x_i=x_i,
        y_i=y_i,
        x_j=x_j,
        y_j=y_j,
        text=text,
        where=where,
        rotate_with_member=rotate_with_member,
        mask=mask,
        normal_offset=normal_offset,
        text_kws=dict(text_kws),
    )
    return out["texts"]


def plan_show_values(
    data: pd.DataFrame,
    *,
    ax=None,
    value: str = "value",
    member: str = "member_id",
    station: str = "station",
    mode: Literal["absmax", "max", "min"] = "absmax",
    value_fmt: str | Callable[[float], str] = "{v:.2f}",
    threshold: float | None = None,
    where: Literal["xy"] = "xy",
    normal_offset: float = 1.5,
    x_i: str = "x_i",
    y_i: str = "y_i",
    x_j: str = "x_j",
    y_j: str = "y_j",
    **text_kws,
):
    """ETABS-like “Show Values”: annotate controlling station per member (axes-level).

    This composes three primitives:
    - select_controlling_stations(...)
    - frames_station_xy(...) to get plan coordinates at the controlling station
    - plan_annotate(where="xy", normal_offset=...)

    Parameters
    ----------
    threshold:
        If provided, only annotate members with abs(value) >= threshold.
    normal_offset:
        Offset (in plan units) along the member normal, to avoid overlapping the marker.

    Returns
    -------
    texts:
        list[matplotlib.text.Text]
    """
    if ax is None:
        ax = plt.gca()

    df_ctrl = select_controlling_stations(
        data=data,
        member=member,
        station=station,
        value=value,
        mode=mode,
    )
    df_ctrl = frames_station_xy(
        data=df_ctrl,
        station=station,
        x_i=x_i,
        y_i=y_i,
        x_j=x_j,
        y_j=y_j,
        out_x="x",
        out_y="y",
    )

    if threshold is not None:
        m = np.abs(df_ctrl[value].to_numpy(float)) >= float(threshold)
        df_ctrl = df_ctrl.loc[df_ctrl.index[m]].copy()

    def _fmt_row(r: pd.Series) -> str:
        v = float(r[value])
        if callable(value_fmt):
            return str(value_fmt(v))
        return str(value_fmt.format(v=v))

    return plan_annotate(
        df_ctrl,
        ax=ax,
        x="x",
        y="y",
        where=where,
        rotate_with_member=True,
        normal_offset=float(normal_offset),
        text=_fmt_row,
        x_i=x_i,
        y_i=y_i,
        x_j=x_j,
        y_j=y_j,
        **text_kws,
    )


def plan_colorbar(
    mappable,
    *,
    ax=None,
    label: str | None = None,
    location: Literal["right", "left", "top", "bottom"] = "bottom",
    **colorbar_kws,
):
    """Attach a colorbar to a mappable (axes-level convenience)."""
    if ax is None:
        ax = plt.gca()
    return _add_colorbar(
        mappable=mappable,
        ax=ax,
        label=label,
        location=location,
        colorbar_kws=dict(colorbar_kws),
    )


