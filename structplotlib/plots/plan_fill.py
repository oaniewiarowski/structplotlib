"""
structplotlib.plots.plan_fill
=============================

Matplotlib plotting utilities.

Two layers:

1) plot_plan / plot_plan_by_story
   - accept *already reduced* data (output of structplotlib.reduce.frame_stations.reduce_plan)
   - no filtering/enveloping

2) plot_fill_plan (convenience wrapper)
   - optional filtering by output_case list
   - optional member-level envelope across cases
   - station-level aggregation + reduction
   - per-story plotting, with optional context lines for unselected frames
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..reduce.frame_stations import Agg, Mode
from ..schema.base import require_columns
from .plan_fill_primitives import (
    _format_value,
    _infer_figsize_from_bbox,
    _is_numeric_series,
    add_colorbar,
    annotate_frames,
    frames_station_xy,
    plot_frames_fill,
    plot_frames_lines,
    prepare_plan_dataframe,
    select_controlling_stations,
)


def plot_plan(
    df_reduced: pd.DataFrame,
    *,
    story: str | None = None,
    value_col: str = "value",
    value_name: str | None = None,
    value_mode: Literal["auto", "numeric", "label"] = "auto",
    ax=None,
    norm_min: float | None = None,
    norm_max: float | None = None,
    k_per_segment: int = 5,
    marker_size: float = 36.0,
    cmap: str = "turbo",
    width_in: float = 14.0,
    title: str | None = None,
    show_colorbar: bool = True,
    show_values: bool = False,
    value_fmt: str | Callable[[float], str] = "{v:.2f}",
    annotate_threshold: float | None = None,
    value_text_color: str = "black",
    value_text_color_above_threshold: str | None = None,
    selected_col: str | None = None,
    others_linewidth: float = 0.5,
    label_shift: float = 1.5,
    fontsize: float = 14.0,
    watermark: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot one story in plan from a reduced dataframe.

    Parameters
    ----------
    df_reduced:
        Output of structplotlib.reduce.frame_stations.reduce_plan (or equivalent).
        Must contain: story, member_id, station, x_i,y_i,x_j,y_j, and value_col.
    story:
        Story to plot. If None, requires df_reduced has exactly one story.
    k_per_segment:
        Number of square markers *per interval between consecutive stations* (visual densification).
    selected_col:
        If provided, rows with selected_col==True are plotted as colored squares, and
        members with selected_col==False are shown as thin black context lines.
    show_values:
        ETABS-style "Show Values": label the controlling value (abs max) once per member.
    annotate_threshold:
        If provided, only annotate members whose controlling |value| >= threshold.
    value_text_color:
        Default color for "Show Values" labels.
    value_text_color_above_threshold:
        If provided and annotate_threshold is provided, use this alternate text color for labels
        whose controlling |value| >= annotate_threshold.

    Notes
    -----
    If the values are non-numeric, or if every member has a single value across all stations,
    the plot switches to a label-only mode: members are drawn as simple lines and the value is
    annotated at the member midpoint (no colormap).

    value_mode:
        - "auto": infer numeric vs label mode from the data
        - "numeric": force numeric coloring (unless member-constant triggers label-only)
        - "label": force label-only mode (useful for categorical values that may look numeric)
    """
    warnings.warn(
        "`plot_plan` is deprecated and will be removed in a future release. "
        "Use axes-level composition (`structplotlib.plan_fill`, `structplotlib.plan_lines`, "
        "`structplotlib.plan_show_values`, `structplotlib.plan_annotate`) or the wrapper "
        "`structplotlib.planplot`.",
        DeprecationWarning,
        stacklevel=2,
    )
    required = {"story", "member_id", "station", "x_i", "y_i", "x_j", "y_j", value_col}
    missing = sorted(required - set(df_reduced.columns))
    if missing:
        raise ValueError(f"[plot_plan] Missing required columns: {missing}")

    df = df_reduced.copy()

    if story is None:
        stories = list(pd.unique(df["story"]))
        if len(stories) != 1:
            raise ValueError(
                f"[plot_plan] story=None but dataframe has {len(stories)} stories: {stories}"
            )
        story = str(stories[0])

    df = df[df["story"] == story].copy()
    if df.empty:
        raise ValueError(f"[plot_plan] No rows for story={story!r}")

    df = df.sort_values(["member_id", "station"], kind="mergesort")

    if value_mode not in ("auto", "numeric", "label"):
        raise ValueError(
            f"[plot_plan] value_mode must be one of 'auto','numeric','label', got {value_mode!r}"
        )
    if value_mode == "numeric":
        value_is_numeric = True
    elif value_mode == "label":
        value_is_numeric = False
    else:
        value_is_numeric = _is_numeric_series(df[value_col])

    member_constant = (
        df.groupby("member_id", sort=False)[value_col].nunique(dropna=False) <= 1
    ).all()
    label_mode = (value_mode == "label") or (not value_is_numeric) or bool(member_constant)

    if (not label_mode) and int(k_per_segment) > 1 and "element" not in df.columns:
        raise ValueError(
            "[plot_plan] k_per_segment>1 (densification) requires an 'element' column. "
            "Include Element/FrameElem in your upstream dataframe (or use plot_fill_plan which normalizes these), "
            "or set k_per_segment=1 to plot only at the provided stations."
        )
    if selected_col is not None and selected_col not in df.columns:
        raise ValueError(
            f"[plot_plan] selected_col={selected_col!r} not found in dataframe columns"
        )

    # Create axes
    if ax is None:
        fig, ax = plt.subplots(figsize=_infer_figsize_from_bbox(df, width_in=width_in))
    else:
        fig = ax.figure

    # Split selected/context (member-level selection must be constant within a member)
    if selected_col is not None:
        g = df.groupby("member_id", sort=False)[selected_col].nunique(dropna=False)
        bad = g[g > 1]
        if not bad.empty:
            mid = str(bad.index[0])
            svals = list(pd.unique(df.loc[df["member_id"] == mid, selected_col]))[:6]
            raise ValueError(
                "[plot_plan] selected_col must be constant within a member_id. "
                f"member_id={mid!r} has values {svals!r}"
            )
        sel_mask = df[selected_col].astype(bool).to_numpy()
        if not np.any(sel_mask) and (not label_mode):
            raise ValueError(
                "[plot_plan] selected_col provided but no members are selected (no colored markers to plot)"
            )
        df_sel = df.loc[sel_mask].copy()
        df_ctx = df.loc[~sel_mask].copy()
    else:
        df_sel = df
        df_ctx = df.iloc[0:0].copy()

    selected_linewidth = max(1.0, float(others_linewidth) * 2.5)

    # Draw context lines first (thin black)
    if not df_ctx.empty:
        plot_frames_lines(
            data=df_ctx,
            ax=ax,
            member="member_id",
            line_kws=dict(color="black", linewidth=float(others_linewidth), zorder=1),
        )

    if label_mode:
        # One segment per selected member
        plot_frames_lines(
            data=df_sel,
            ax=ax,
            member="member_id",
            line_kws=dict(color="black", linewidth=float(selected_linewidth), zorder=2),
        )

        # One label per member at midpoint
        df_one = (
            df_sel.sort_values(["member_id", "station"], kind="mergesort")
            .groupby("member_id", sort=False, as_index=False)
            .first()
            .copy()
        )
        nunique = df_sel.groupby("member_id", sort=False)[value_col].nunique(dropna=False)
        bad = nunique[nunique > 1]
        if not bad.empty:
            mid = str(bad.index[0])
            examples = list(pd.unique(df_sel.loc[df_sel["member_id"] == mid, value_col]))[:6]
            raise ValueError(
                "[plot_plan] label-only mode requires values to be constant within each member_id. "
                f"member_id={mid!r} has {int(bad.iloc[0])} distinct values in {value_col!r}. "
                f"Examples: {examples!r}"
            )

        if value_is_numeric:
            vals = df_one[value_col].to_numpy(float)
            if annotate_threshold is not None:
                m = np.abs(vals) >= float(annotate_threshold)
                df_one = df_one.loc[df_one.index[m]].copy()
                txt_color = (
                    str(value_text_color_above_threshold)
                    if value_text_color_above_threshold is not None
                    else str(value_text_color)
                )
            else:
                txt_color = str(value_text_color)
            annotate_frames(
                data=df_one,
                ax=ax,
                text=lambda r: _format_value(float(r[value_col]), value_fmt),
                where="midpoint",
                rotate_with_member=True,
                text_kws=dict(fontsize=float(fontsize), color=txt_color),
            )
        else:
            annotate_frames(
                data=df_one,
                ax=ax,
                text=lambda r: str(r[value_col]),
                where="midpoint",
                rotate_with_member=True,
                text_kws=dict(fontsize=float(fontsize), color=str(value_text_color)),
            )
    else:
        # Norm scaling (selected-only if selection is active)
        vals_for_norm = df_sel[value_col].to_numpy(float)
        if norm_min is None:
            norm_min = float(np.min(vals_for_norm))
        if norm_max is None:
            norm_max = float(np.max(vals_for_norm))

        out = plot_frames_fill(
            data=df_sel,
            ax=ax,
            member="member_id",
            station="station",
            value=value_col,
            densify=("linear" if int(k_per_segment) > 1 else "none"),
            k_per_segment=int(k_per_segment),
            cmap=str(cmap),
            vmin=norm_min,
            vmax=norm_max,
            scatter_kws=dict(s=float(marker_size), marker="s", linewidths=0, alpha=0.95, zorder=3),
        )
        if show_colorbar:
            add_colorbar(
                mappable=out["markers"],
                ax=ax,
                label=(value_name or value_col),
                location="bottom",
                colorbar_kws=dict(fraction=0.05, pad=0.0, aspect=10),
            )

        if show_values:
            df_ctrl = select_controlling_stations(
                data=df_sel, member="member_id", station="station", value=value_col, mode="absmax"
            )
            df_ctrl = frames_station_xy(data=df_ctrl, station="station", out_x="x", out_y="y")
            vals = df_ctrl[value_col].to_numpy(float)
            if annotate_threshold is not None:
                m = np.abs(vals) >= float(annotate_threshold)
                df_ctrl = df_ctrl.loc[df_ctrl.index[m]].copy()
                txt_color = (
                    str(value_text_color_above_threshold)
                    if value_text_color_above_threshold is not None
                    else str(value_text_color)
                )
            else:
                txt_color = str(value_text_color)
            annotate_frames(
                data=df_ctrl,
                ax=ax,
                x="x",
                y="y",
                text=lambda r: _format_value(float(r[value_col]), value_fmt),
                where="xy",
                rotate_with_member=True,
                normal_offset=float(label_shift),
                text_kws=dict(fontsize=float(fontsize), color=txt_color),
            )

    ax.set_aspect("equal", adjustable="datalim")
    ax.axis("off")

    if title is None:
        title = f"{story} — {(value_name or value_col)}"
    ax.set_title(title)

    if watermark:
        ax.text(
            0.99,
            0.01,
            watermark,
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=max(8.0, float(fontsize) * 0.7),
            alpha=0.5,
            zorder=10,
        )

    return fig, ax


def plot_plan_by_story(df_reduced: pd.DataFrame, **kwargs):
    """Return {story: (fig, ax)} for each story present in the dataframe."""
    warnings.warn(
        "`plot_plan_by_story` is deprecated and will be removed in a future release. "
        "Use `structplotlib.planplot(..., story=None)` for multi-story wrappers, or loop over "
        "stories and call axes-level functions (`plan_fill` / `plan_lines`) yourself.",
        DeprecationWarning,
        stacklevel=2,
    )
    require_columns(df_reduced, ["story"], where="plot_plan_by_story")
    out = {}
    for story in pd.unique(df_reduced["story"]):
        fig, ax = plot_plan(df_reduced, story=str(story), **kwargs)
        out[str(story)] = (fig, ax)
    return out


def plot_fill_plan(
    df: pd.DataFrame,
    *,
    source: Literal["etabs", "sap2000"] | None = None,
    table: str = "frame_dcr",
    normalize: bool = True,
    strict: bool = True,
    enforce_preferred_input_names: bool = False,
    value_col: str,
    value_mode: Literal["auto", "numeric", "label"] = "auto",
    cases: list[str] | None = None,
    envelope: bool | None = None,
    reduction_mode: Mode = "absmax",
    station_agg: Agg = "max",
    step_type: str | None = None,
    story_name: str | None = None,
    output_case_label: str | None = None,
    frame_filter: pd.Series | list[bool] | None = None,
    value_name: str | None = None,
    norm_min: float | None = None,
    norm_max: float | None = None,
    k_per_segment: int = 5,
    marker_size: float = 36.0,
    show_values: bool = False,
    value_fmt: str | Callable[[float], str] = "{v:.2f}",
    annotate_threshold: float | None = None,
    value_text_color: str = "black",
    value_text_color_above_threshold: str | None = None,
    others_linewidth: float = 0.5,
    label_shift: float = 1.5,
    fontsize: float = 14.0,
    watermark: str | None = None,
    cmap: str = "turbo",
    width_in: float = 14.0,
    show_colorbar: bool = True,
    return_df: bool = False,
):
    """Convenience wrapper: filter/envelope/reduce and plot one figure per story.

    This is the ergonomic "one call" API.

    - If `cases` is provided, filters to those output_case values first.
    - If `envelope` is True, selects governing case triple per member across the cases.
      If `envelope` is None, defaults to True when len(cases) > 1.
    - Duplicates are aggregated per station (default: max).
    - If `frame_filter` is provided, members with False are drawn as thin black lines.

    Returns
    -------
    figs_dict:
        {story: (fig, ax)}
    dfs_dict (optional):
        {story: df_reduced_used_for_plot}

        Notes: when return_df=True, the returned per-story dataframe includes an ``output_case`` column
        to aid debugging of which governing case was used for each plotted member.
    """
    warnings.warn(
        "`plot_fill_plan` is deprecated and will be removed in a future release. "
        "Use `structplotlib.planplot` for the wrapper behavior, or compose the pipeline explicitly "
        "(`normalize_df`/`filter_cases`/`envelope_by_member`/`reduce_plan`) plus axes-level plotting "
        "(`plan_fill`, `plan_show_values`, etc.).",
        DeprecationWarning,
        stacklevel=2,
    )
    prep = prepare_plan_dataframe(
        df,
        source=source,
        table=table,
        normalize=normalize,
        strict=strict,
        enforce_preferred_input_names=enforce_preferred_input_names,
        value_col=value_col,
        value_mode=value_mode,
        cases=cases,
        envelope=envelope,
        reduction_mode=reduction_mode,
        station_agg=station_agg,
        step_type=step_type,
        story_name=story_name,
    )

    df_red = prep.df.copy()

    # Member selection map from frame_filter (context vs selected)
    selected_col = None
    if frame_filter is not None:
        df0 = df.copy()
        if story_name is not None and "story" in df0.columns:
            df0 = df0[df0["story"] == story_name].copy()
        if isinstance(frame_filter, list):
            frame_filter = pd.Series(frame_filter, index=df0.index)
        else:
            frame_filter = pd.Series(frame_filter, index=df0.index)
        if len(frame_filter) != len(df0):
            raise ValueError(
                "[plot_fill_plan] frame_filter must be the same length as df after story_name filtering"
            )
        df0["_selected_row"] = frame_filter.astype(bool).to_numpy()
        g = df0.groupby(["story", "member_id"], sort=False)["_selected_row"].nunique(dropna=False)
        bad = g[g > 1]
        if not bad.empty:
            offenders = list(bad.index[:8])
            raise ValueError(
                "[plot_fill_plan] frame_filter must be constant within each (story, member_id). "
                f"Examples with mixed True/False: {offenders}"
            )
        selected_map = (
            df0.groupby(["story", "member_id"], sort=False, as_index=False)["_selected_row"]
            .first()
            .rename(columns={"_selected_row": "selected"})
        )
        df_red = df_red.merge(selected_map, on=["story", "member_id"], how="left")
        df_red["selected"] = df_red["selected"].fillna(True).astype(bool)
        selected_col = "selected"

    # Densification requirement: preserve legacy behavior
    if (
        (not prep.label_only)
        and prep.value_is_numeric
        and int(k_per_segment) > 1
        and "element" not in df_red.columns
    ):
        raise ValueError(
            "[plot_fill_plan] k_per_segment>1 (densification) requires an 'element' column. "
            "Export element-level results that include Element/FrameElem (and ideally Elem Station), "
            "or set k_per_segment=1 to plot only at the provided stations."
        )

    # Label for title
    if output_case_label is None:
        if prep.envelope:
            output_case_label = f"Envelope({reduction_mode})"
        elif prep.cases_eff:
            output_case_label = str(prep.cases_eff[0])

    figs = {}
    dfs = {}
    for st in pd.unique(df_red["story"]):
        title_parts = [str(st)]
        if output_case_label:
            title_parts.append(str(output_case_label))
        title_parts.append(str(value_name or value_col))
        title = " — ".join(title_parts)

        df_story = df_red[df_red["story"] == st].copy()
        fig, ax = plot_plan(
            df_story,
            story=str(st),
            value_col="value",
            value_name=value_name or value_col,
            value_mode=("label" if prep.label_only else "auto"),
            norm_min=norm_min,
            norm_max=norm_max,
            k_per_segment=k_per_segment,
            marker_size=marker_size,
            cmap=cmap,
            width_in=width_in,
            title=title,
            show_colorbar=show_colorbar,
            show_values=show_values,
            value_fmt=value_fmt,
            annotate_threshold=annotate_threshold,
            value_text_color=value_text_color,
            value_text_color_above_threshold=value_text_color_above_threshold,
            selected_col=selected_col,
            others_linewidth=others_linewidth,
            label_shift=label_shift,
            fontsize=fontsize,
            watermark=watermark,
        )
        figs[str(st)] = (fig, ax)
        if return_df:
            dfs[str(st)] = df_story.reset_index(drop=True)

    return (figs, dfs) if return_df else figs
