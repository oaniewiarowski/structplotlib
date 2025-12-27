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

from collections.abc import Callable
from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

from ..reduce.frame_stations import (
    Agg,
    Mode,
    envelope_by_member,
    filter_cases,
    reduce_plan,
)
from ..schema.base import require_columns
from ..schema.csi import normalize_df, resolve_canonical_name


def _infer_figsize_from_bbox(df: pd.DataFrame, width_in: float) -> tuple[float, float]:
    x = np.concatenate([df["x_i"].to_numpy(float), df["x_j"].to_numpy(float)])
    y = np.concatenate([df["y_i"].to_numpy(float), df["y_j"].to_numpy(float)])
    w = max(1e-9, float(np.max(x) - np.min(x)))
    h = max(1e-9, float(np.max(y) - np.min(y)))
    height_in = width_in * (h / w)
    height_in = min(max(height_in, width_in * 0.3), width_in * 3.0)
    return (width_in, height_in)


def _format_value(v: float, value_fmt: str | Callable[[float], str]) -> str:
    if callable(value_fmt):
        return str(value_fmt(float(v)))
    # format-string style: "{v:.2f}"
    return str(value_fmt.format(v=float(v)))


def _is_numeric_series(series: pd.Series) -> bool:
    if is_numeric_dtype(series):
        return True
    non_null = series.dropna()
    if non_null.empty:
        return False
    coerced = pd.to_numeric(non_null, errors="coerce")
    return coerced.notna().all()


def plot_plan(
    df_reduced: pd.DataFrame,
    *,
    story: str | None = None,
    value_col: str = "value",
    value_name: str | None = None,
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
    """
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
    value_series = df[value_col]
    value_is_numeric = _is_numeric_series(value_series)
    member_constant = (
        df.groupby("member_id", sort=False)[value_col].nunique(dropna=False) <= 1
    ).all()
    label_mode = (not value_is_numeric) or member_constant
    if selected_col is not None and selected_col not in df.columns:
        raise ValueError(
            f"[plot_plan] selected_col={selected_col!r} not found in dataframe columns"
        )

    # Create axes
    if ax is None:
        fig, ax = plt.subplots(figsize=_infer_figsize_from_bbox(df, width_in=width_in))
    else:
        fig = ax.figure

    # Decide which rows contribute colored markers / colormap scaling
    if not label_mode:
        if selected_col is not None:
            sel_mask = df[selected_col].astype(bool).to_numpy()
            if not np.any(sel_mask):
                raise ValueError(
                    "[plot_plan] selected_col provided but no members are selected (no colored markers to plot)"
                )
            vals_for_norm = df.loc[sel_mask, value_col].to_numpy(float)
        else:
            vals_for_norm = df[value_col].to_numpy(float)

        if norm_min is None:
            norm_min = float(np.min(vals_for_norm))
        if norm_max is None:
            norm_max = float(np.max(vals_for_norm))

    xs_all, ys_all, vals_all = [], [], []
    labels = []  # (x,y,text,angle_deg,color)
    context_lines = []  # (xi,yi,xj,yj)
    member_lines = []  # (xi,yi,xj,yj,linewidth)
    selected_linewidth = max(1.0, float(others_linewidth) * 2.5)

    for mid, g in df.groupby("member_id", sort=False):
        r0 = g.iloc[0]
        xi, yi, xj, yj = (
            float(r0["x_i"]),
            float(r0["y_i"]),
            float(r0["x_j"]),
            float(r0["y_j"]),
        )
        dx, dy = xj - xi, yj - yi
        member_len = float(np.hypot(dx, dy))
        if member_len < 1e-12:
            # degenerate in plan; skip densification, but still allow annotation at the point
            member_len = 1.0

        # Member-level selection
        selected = True
        if selected_col is not None:
            svals = pd.unique(g[selected_col])
            if len(svals) != 1:
                raise ValueError(
                    f"[plot_plan] selected_col must be constant within a member_id. member_id={mid!r} has values {list(svals)!r}"
                )
            selected = bool(svals[0])

        if not selected:
            context_lines.append((xi, yi, xj, yj))
            if label_mode:
                continue
            else:
                continue

        if label_mode:
            member_lines.append((xi, yi, xj, yj, selected_linewidth))
            v_label = g[value_col].iloc[0]
            if value_is_numeric:
                v_label = float(v_label)
                if (annotate_threshold is not None) and (
                    abs(v_label) < float(annotate_threshold)
                ):
                    continue
                label_text = _format_value(v_label, value_fmt)
            else:
                label_text = str(v_label)
            xm = 0.5 * (xi + xj)
            ym = 0.5 * (yi + yj)
            ang = float(np.degrees(np.arctan2(dy, dx)))
            color = str(value_text_color)
            if (
                value_is_numeric
                and annotate_threshold is not None
                and value_text_color_above_threshold is not None
                and abs(v_label) >= float(annotate_threshold)
            ):
                color = str(value_text_color_above_threshold)
            labels.append((xm, ym, label_text, ang, color))
            continue

        st = g["station"].to_numpy(float)
        vv = g[value_col].to_numpy(float)

        # Ensure station is sorted ascending for interpolation
        order = np.argsort(st, kind="mergesort")
        st = st[order]
        vv = vv[order]

        # Parameter along member: station assumed to be distance from I-end (length units)
        t_raw = st / member_len

        if t_raw.size == 1 or k_per_segment < 2:
            t_dense = t_raw
        else:
            # densify per interval between stations
            chunks = [
                np.linspace(t_raw[i], t_raw[i + 1], k_per_segment, endpoint=False)
                for i in range(t_raw.size - 1)
            ]
            t_dense = np.concatenate(chunks + [np.array([t_raw[-1]])])

        v_dense = np.interp(t_dense, t_raw, vv)
        xs = xi + dx * t_dense
        ys = yi + dy * t_dense

        xs_all.append(xs)
        ys_all.append(ys)
        vals_all.append(v_dense)

        if show_values:
            # controlling station: abs max
            i_ctrl = int(np.argmax(np.abs(vv)))
            v_ctrl = float(vv[i_ctrl])
            if (annotate_threshold is None) or (abs(v_ctrl) >= float(annotate_threshold)):
                t_ctrl = float(t_raw[i_ctrl])
                xm = xi + dx * t_ctrl
                ym = yi + dy * t_ctrl

                # shift label along unit normal to the member
                nx, ny = (-dy / member_len, dx / member_len)
                xm += nx * float(label_shift)
                ym += ny * float(label_shift)

                ang = float(np.degrees(np.arctan2(dy, dx)))
                color = str(value_text_color)
                if (
                    annotate_threshold is not None
                    and value_text_color_above_threshold is not None
                    and abs(v_ctrl) >= float(annotate_threshold)
                ):
                    color = str(value_text_color_above_threshold)
                labels.append((xm, ym, _format_value(v_ctrl, value_fmt), ang, color))

    # Context lines first (thin black)
    for xi, yi, xj, yj in context_lines:
        ax.plot(
            [xi, xj],
            [yi, yj],
            color="black",
            linewidth=float(others_linewidth),
            zorder=1,
        )

    for xi, yi, xj, yj, lw in member_lines:
        ax.plot([xi, xj], [yi, yj], color="black", linewidth=lw, zorder=2)

    if xs_all:
        xs_all = np.concatenate(xs_all)
        ys_all = np.concatenate(ys_all)
        vals = np.concatenate(vals_all)

        sc = ax.scatter(
            xs_all,
            ys_all,
            s=float(marker_size),
            c=vals,
            cmap=plt.get_cmap(cmap),
            vmin=norm_min,
            vmax=norm_max,
            marker="s",
            linewidths=0,
            alpha=0.95,
            zorder=3,
        )

        if show_colorbar:
            cb = fig.colorbar(sc, ax=ax, location="bottom", fraction=0.05, pad=0.0, aspect=10)
            cb.set_label(value_name or value_col)
    else:
        sc = None  # no selected markers

    for x, y, txt, ang, color in labels:
        ax.text(
            x,
            y,
            txt,
            ha="center",
            va="bottom",
            rotation=ang,
            rotation_mode="anchor",
            fontsize=float(fontsize),
            color=color,
            zorder=5,
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

    # Optional boundary normalization: allow passing raw ETABS/SAP exports directly.
    value_col_eff = value_col

    if normalize:
        # If already canonical (except optional story), do not require `source`.
        canonical_no_story = {
            "member_id",
            "station",
            "output_case",
            "case_type",
            "step_type",
            "x_i",
            "y_i",
            "x_j",
            "y_j",
        }
        if not canonical_no_story.issubset(set(df.columns)):
            if source is None:
                raise ValueError(
                    "[plot_fill_plan] normalize=True but dataframe is not canonical and source=None. "
                    "Pass source='etabs' or source='sap2000', or call structplotlib.schema.normalize_df/load_df upstream."
                )
            df = normalize_df(
                df,
                source=source,
                table=table,
                strict=strict,
                enforce_preferred_input_names=enforce_preferred_input_names,
            )

        # If the user specified an input/header spelling that got renamed during normalization,
        # resolve it to the canonical column name.
        if value_col_eff not in df.columns and source is not None:
            canon = resolve_canonical_name(value_col_eff, source=source, table=table)
            if canon is not None and canon in df.columns:
                value_col_eff = canon
    else:
        # normalize=False: interpret value_col as-is
        pass

    # minimal canonical-ish requirements (defaults applied below)
    if "story" not in df.columns:
        df = df.copy()
        df["story"] = "ALL"
    if "step_type" not in df.columns:
        df = df.copy()
        df["step_type"] = ""

    require_columns(
        df,
        [
            "story",
            "member_id",
            "station",
            "output_case",
            "case_type",
            "step_type",
            "x_i",
            "y_i",
            "x_j",
            "y_j",
            value_col_eff,
        ],
        where="plot_fill_plan",
    )
    value_is_numeric = _is_numeric_series(df[value_col_eff])

    df0 = df.copy()
    if story_name is not None:
        df0 = df0[df0["story"] == story_name].copy()

    # Member selection map from frame_filter
    selected_map = None
    if frame_filter is not None:
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
        df0 = df0.drop(columns=["_selected_row"])

    # Filter cases
    df1 = filter_cases(df0, cases)

    # Determine envelope default
    if cases is None:
        cases_eff = list(pd.unique(df1["output_case"]))
    else:
        cases_eff = list(cases)
    if envelope is None:
        envelope = value_is_numeric and len(cases_eff) > 1
    if (not value_is_numeric) and envelope:
        envelope = False

    if envelope:
        df2 = envelope_by_member(
            df1, value_col=value_col_eff, mode=reduction_mode, station_agg=station_agg
        )
    else:
        df2 = df1.copy()
        # If multiple step types exist, force the user to pick one (unless they already filtered upstream)
        steps = list(pd.unique(df2["step_type"]))
        if step_type is not None:
            if step_type not in steps:
                raise ValueError(
                    f"[plot_fill_plan] step_type={step_type!r} not found. Available: {steps}"
                )
            df2 = df2[df2["step_type"] == step_type].copy()
        else:
            if len(steps) > 1:
                raise ValueError(
                    f"[plot_fill_plan] Multiple step_type values exist for non-envelope plot: {steps}. Pass step_type=... or prefilter upstream."
                )

    # Reduce to plot-ready
    df_red = reduce_plan(df2, value_col=value_col_eff, station_agg=station_agg)

    # Attach selection info
    if selected_map is not None:
        df_red = df_red.merge(selected_map, on=["story", "member_id"], how="left")
        df_red["selected"] = df_red["selected"].fillna(True).astype(bool)
        selected_col = "selected"
    else:
        selected_col = None

    # Label for title
    if output_case_label is None:
        if envelope:
            output_case_label = f"Envelope({reduction_mode})"
        elif cases_eff:
            output_case_label = str(cases_eff[0])

    figs = {}
    dfs = {}
    for story in pd.unique(df_red["story"]):
        title_parts = [str(story)]
        if output_case_label:
            title_parts.append(str(output_case_label))
        title_parts.append(str(value_name or value_col))
        title = " — ".join(title_parts)

        df_story = df_red[df_red["story"] == story].copy()
        fig, ax = plot_plan(
            df_story,
            story=str(story),
            value_col="value",
            value_name=value_name or value_col,
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
        figs[str(story)] = (fig, ax)
        if return_df:
            dfs[str(story)] = df_story.reset_index(drop=True)

    return (figs, dfs) if return_df else figs
