"""
structplotlib.plots.plan_fill_primitives
========================================

Composable Matplotlib-ish primitives for plan-view frame plots.

This module is the refactoring target for the legacy `structplotlib.plots.plan_fill` logic.
It exposes small render/annotation primitives and a few data-prep helpers so users can
compose the exact same plots without a monolithic wrapper.

Design principles
-----------------
- Separate geometry lines vs numeric "fill" markers vs annotation.
- No concept of "context geometry" baked in. Users call the same primitives multiple
  times with different subsets/styles.
- Prefer `data=...` + column-name strings; accept callables for text formatting.
- Return Matplotlib artists for post-hoc tweaking and for tests.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

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

_DEFAULT_LABEL_COLS = {"member_id", "output_case", "case_type", "step_type"}


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
    return str(value_fmt.format(v=float(v)))


def _is_numeric_series(series: pd.Series) -> bool:
    if is_numeric_dtype(series):
        return True
    non_null = series.dropna()
    if non_null.empty:
        return False
    coerced = pd.to_numeric(non_null, errors="coerce")
    return coerced.notna().all()


def plot_frames_lines(
    *,
    data: pd.DataFrame,
    ax=None,
    x_i: str = "x_i",
    y_i: str = "y_i",
    x_j: str = "x_j",
    y_j: str = "y_j",
    member: str | None = "member_id",
    story: str | None = "story",
    story_value: str | None = None,
    line_kws: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Draw member centerlines as line segments in plan.

    Notes
    -----
    - If `member` is provided, one segment per unique member is drawn (first row per member).
    - If `member=None`, every row is drawn as its own segment.
    - No filtering/enveloping/reduction is performed here.
    """
    if line_kws is None:
        line_kws = {}
    df = data
    if story_value is not None and story is not None and story in df.columns:
        df = df[df[story] == story_value]

    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.figure

    if df.empty:
        return {"fig": fig, "ax": ax, "lines": []}

    if member is not None and member in df.columns:
        # stable first-per-member
        df = (
            df.sort_values([member], kind="mergesort")
            .groupby(member, sort=False, as_index=False)
            .first()
        )

    artists = []
    for _, r in df.iterrows():
        (ln,) = ax.plot(
            [float(r[x_i]), float(r[x_j])],
            [float(r[y_i]), float(r[y_j])],
            **line_kws,
        )
        artists.append(ln)
    return {"fig": fig, "ax": ax, "lines": artists}


def plot_frames_fill(
    *,
    data: pd.DataFrame,
    ax=None,
    x_i: str = "x_i",
    y_i: str = "y_i",
    x_j: str = "x_j",
    y_j: str = "y_j",
    member: str = "member_id",
    station: str = "station",
    value: str = "value",
    element: str | None = "element",
    densify: Literal["none", "linear"] = "linear",
    k_per_segment: int = 5,
    cmap: str = "turbo",
    norm=None,
    vmin: float | None = None,
    vmax: float | None = None,
    scatter_kws: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Draw numeric station results as colored square markers along members.

    This is the "fill" renderer: it maps station positions to (x,y) along each member,
    optionally densifying linearly between stations and treating duplicate-station sequences
    as discontinuities (to preserve element-boundary left/right values).
    """
    if scatter_kws is None:
        scatter_kws = {}
    df = data
    required = {member, station, x_i, y_i, x_j, y_j, value}
    missing = sorted([c for c in required if c not in df.columns])
    if missing:
        raise ValueError(f"[plot_frames_fill] Missing required columns: {missing}")

    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.figure

    xs_all: list[np.ndarray] = []
    ys_all: list[np.ndarray] = []
    vals_all: list[np.ndarray] = []

    for _mid, g in df.groupby(member, sort=False):
        r0 = g.iloc[0]
        xi, yi, xj, yj = (
            float(r0[x_i]),
            float(r0[y_i]),
            float(r0[x_j]),
            float(r0[y_j]),
        )
        dx, dy = xj - xi, yj - yi
        member_len = float(np.hypot(dx, dy))
        if member_len < 1e-12:
            member_len = 1.0

        st = g[station].to_numpy(float)
        vv = g[value].to_numpy(float)

        order = np.argsort(st, kind="mergesort")
        st = st[order]
        vv = vv[order]

        t_raw = st / member_len
        split_idx = np.where(np.diff(t_raw) <= 0)[0] + 1
        seg_idxs = np.split(np.arange(t_raw.size), split_idx) if t_raw.size else []

        t_dense_parts: list[np.ndarray] = []
        v_dense_parts: list[np.ndarray] = []
        for seg in seg_idxs:
            t_seg = t_raw[seg]
            v_seg = vv[seg]
            if densify == "none" or int(k_per_segment) < 2 or t_seg.size == 1:
                t_d = t_seg
                v_d = v_seg
            else:
                chunks = [
                    np.linspace(t_seg[i], t_seg[i + 1], int(k_per_segment), endpoint=False)
                    for i in range(t_seg.size - 1)
                ]
                t_d = np.concatenate(chunks + [np.array([t_seg[-1]])])
                v_d = np.interp(t_d, t_seg, v_seg)
            t_dense_parts.append(t_d)
            v_dense_parts.append(v_d)

        t_dense = np.concatenate(t_dense_parts) if t_dense_parts else t_raw
        v_dense = np.concatenate(v_dense_parts) if v_dense_parts else vv
        xs = xi + dx * t_dense
        ys = yi + dy * t_dense

        xs_all.append(xs)
        ys_all.append(ys)
        vals_all.append(v_dense)

    if not xs_all:
        # Empty scatter
        sc = ax.scatter([], [], c=[], cmap=plt.get_cmap(cmap), vmin=vmin, vmax=vmax)
        return {"fig": fig, "ax": ax, "markers": sc, "norm": sc.norm, "cmap": sc.cmap}

    xs_cat = np.concatenate(xs_all)
    ys_cat = np.concatenate(ys_all)
    vals = np.concatenate(vals_all)

    if vmin is None:
        vmin = float(np.min(vals)) if vals.size else None
    if vmax is None:
        vmax = float(np.max(vals)) if vals.size else None

    kws = dict(
        s=36.0,
        marker="s",
        linewidths=0,
        alpha=0.95,
        zorder=3,
    )
    kws.update(scatter_kws)
    sc = ax.scatter(
        xs_cat,
        ys_cat,
        c=vals,
        cmap=plt.get_cmap(cmap),
        norm=norm,
        vmin=vmin,
        vmax=vmax,
        **kws,
    )
    return {"fig": fig, "ax": ax, "markers": sc, "norm": sc.norm, "cmap": sc.cmap}


def frames_station_xy(
    *,
    data: pd.DataFrame,
    station: str = "station",
    x_i: str = "x_i",
    y_i: str = "y_i",
    x_j: str = "x_j",
    y_j: str = "y_j",
    out_x: str = "x",
    out_y: str = "y",
) -> pd.DataFrame:
    """Compute (x,y) along each member at the provided station values.

    This matches the legacy mapping used by `plot_plan` for "Show Values" controlling stations.
    """
    require_columns(data, [station, x_i, y_i, x_j, y_j], where="frames_station_xy")
    df = data.copy()
    xi = df[x_i].to_numpy(float)
    yi = df[y_i].to_numpy(float)
    xj = df[x_j].to_numpy(float)
    yj = df[y_j].to_numpy(float)
    dx = xj - xi
    dy = yj - yi
    L = np.hypot(dx, dy)
    L = np.where(L < 1e-12, 1.0, L)
    t = df[station].to_numpy(float) / L
    df[out_x] = xi + dx * t
    df[out_y] = yi + dy * t
    return df


def select_controlling_stations(
    *,
    data: pd.DataFrame,
    member: str = "member_id",
    station: str = "station",
    value: str = "value",
    mode: Literal["absmax", "max", "min"] = "absmax",
) -> pd.DataFrame:
    """Return a per-member subset containing the controlling station row."""
    require_columns(data, [member, station, value], where="select_controlling_stations")
    idxs: list[int] = []
    for _mid, g in data.groupby(member, sort=False):
        vv = g[value].to_numpy(float)
        if vv.size == 0:
            continue
        if mode == "absmax":
            j = int(np.argmax(np.abs(vv)))
        elif mode == "max":
            j = int(np.argmax(vv))
        elif mode == "min":
            j = int(np.argmin(vv))
        else:
            raise ValueError(
                f"[select_controlling_stations] mode must be one of 'absmax','max','min', got {mode!r}"
            )
        idxs.append(int(g.index[j]))
    return data.loc[idxs].copy()


def annotate_frames(
    *,
    data: pd.DataFrame,
    ax=None,
    x: str | None = None,
    y: str | None = None,
    x_i: str = "x_i",
    y_i: str = "y_i",
    x_j: str = "x_j",
    y_j: str = "y_j",
    text: str | Callable[[pd.Series], str] = "member_id",
    where: Literal["midpoint", "i_end", "j_end", "xy"] = "midpoint",
    rotate_with_member: bool = True,
    mask: Sequence[bool] | None = None,
    normal_offset: float = 0.0,
    text_kws: dict[str, Any] | None = None,
    threshold_col: str | None = None,
    threshold: float | None = None,
    text_color_above_threshold: str | None = None,
) -> dict[str, Any]:
    """Annotate members/rows with text at a specified anchor."""
    if text_kws is None:
        text_kws = {}
    df = data
    if mask is not None:
        mask_arr = np.asarray(list(mask), dtype=bool)
        if mask_arr.size != len(df):
            raise ValueError("[annotate_frames] mask must be the same length as data")
        df = df.loc[df.index[mask_arr]].copy()

    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.figure

    # Determine anchors
    if where == "xy":
        if x is None or y is None:
            raise ValueError("[annotate_frames] where='xy' requires x=... and y=...")
        xs = df[x].to_numpy(float)
        ys = df[y].to_numpy(float)
        # Even when anchoring at explicit x/y, we can rotate/offset using member endpoints.
        if rotate_with_member or float(normal_offset) != 0.0:
            xi = df[x_i].to_numpy(float)
            yi = df[y_i].to_numpy(float)
            xj = df[x_j].to_numpy(float)
            yj = df[y_j].to_numpy(float)
            dx = xj - xi
            dy = yj - yi
            L = np.hypot(dx, dy)
            Ls = np.where(L < 1e-12, 1.0, L)
            angs = np.degrees(np.arctan2(dy, dx)) if rotate_with_member else np.zeros(len(df))
            nx = -dy / Ls
            ny = dx / Ls
        else:
            angs = np.zeros(len(df), dtype=float)
            nx = np.zeros(len(df), dtype=float)
            ny = np.zeros(len(df), dtype=float)
    else:
        xi = df[x_i].to_numpy(float)
        yi = df[y_i].to_numpy(float)
        xj = df[x_j].to_numpy(float)
        yj = df[y_j].to_numpy(float)
        dx = xj - xi
        dy = yj - yi
        L = np.hypot(dx, dy)
        Ls = np.where(L < 1e-12, 1.0, L)
        if where == "midpoint":
            xs = 0.5 * (xi + xj)
            ys = 0.5 * (yi + yj)
        elif where == "i_end":
            xs, ys = xi, yi
        elif where == "j_end":
            xs, ys = xj, yj
        else:
            raise ValueError(
                f"[annotate_frames] where must be one of 'midpoint','i_end','j_end','xy', got {where!r}"
            )

        if rotate_with_member:
            angs = np.degrees(np.arctan2(dy, dx))
        else:
            angs = np.zeros(len(df), dtype=float)
        nx = -dy / Ls
        ny = dx / Ls

    xs = xs + float(normal_offset) * nx
    ys = ys + float(normal_offset) * ny

    def _get_text(row: pd.Series) -> str:
        if callable(text):
            return str(text(row))
        if isinstance(text, str) and text in row.index:
            return str(row[text])
        return str(text)

    colors = None
    if threshold_col is not None and threshold is not None and text_color_above_threshold is not None:
        vals = df[threshold_col].to_numpy(float)
        colors = np.where(np.abs(vals) >= float(threshold), str(text_color_above_threshold), None)

    artists = []
    for i, (_idx, row) in enumerate(df.iterrows()):
        kws = dict(
            ha="center",
            va="bottom",
            rotation=float(angs[i]),
            rotation_mode="anchor",
            zorder=5,
        )
        kws.update(text_kws)
        if colors is not None and colors[i] is not None:
            kws["color"] = str(colors[i])
        t = ax.text(float(xs[i]), float(ys[i]), _get_text(row), **kws)
        artists.append(t)
    return {"fig": fig, "ax": ax, "texts": artists}


def add_colorbar(
    *,
    mappable,
    ax,
    label: str | None = None,
    location: Literal["right", "left", "top", "bottom"] = "bottom",
    colorbar_kws: dict[str, Any] | None = None,
):
    """Attach a colorbar to a mappable (e.g. the PathCollection returned by plot_frames_fill)."""
    if colorbar_kws is None:
        colorbar_kws = {}
    fig = ax.figure
    cb = fig.colorbar(mappable, ax=ax, location=location, **colorbar_kws)
    if label is not None:
        cb.set_label(str(label))
    return cb


@dataclass(frozen=True)
class PreparedPlan:
    """Output of `prepare_plan_dataframe`."""

    df: pd.DataFrame
    value_col: str
    label_only: bool
    value_is_numeric: bool
    envelope: bool
    cases_eff: list[str]


def prepare_plan_dataframe(
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
) -> PreparedPlan:
    """Prepare a canonical, reduced dataframe suitable for plotting.

    This is the non-plotting refactor of the legacy `plot_fill_plan` pipeline:
    - optional normalization to canonical schema
    - optional case filtering
    - optional member-level envelope across cases
    - station-level aggregation + reduction to a plot-friendly dataframe

    The output can be fed into:
    - label_only=True: `plot_frames_lines` + `annotate_frames(where="midpoint", text=value_col)`
    - label_only=False: `plot_frames_fill` (+ optional `select_controlling_stations` + `annotate_frames`)
    """
    value_col_eff = value_col
    if normalize:
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
                    "[prepare_plan_dataframe] normalize=True but dataframe is not canonical and source=None. "
                    "Pass source='etabs' or source='sap2000', or call structplotlib.schema.normalize_df/load_df upstream."
                )
            df = normalize_df(
                df,
                source=source,
                table=table,
                strict=strict,
                enforce_preferred_input_names=enforce_preferred_input_names,
            )
        if value_col_eff not in df.columns and source is not None:
            canon = resolve_canonical_name(value_col_eff, source=source, table=table)
            if canon is not None and canon in df.columns:
                value_col_eff = canon

    # defaults for commonly-missing columns
    if "story" not in df.columns:
        df = df.copy()
        df["story"] = "ALL"
    if "step_type" not in df.columns:
        df = df.copy()
        df["step_type"] = ""
    else:
        df = df.copy()
        st = df["step_type"]
        st = st.where(~st.isna(), "")
        if st.dtype == object or str(st.dtype).startswith("string"):
            st = st.replace({"nan": "", "NaN": "", "<NA>": ""})
        df["step_type"] = st

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
        where="prepare_plan_dataframe",
    )

    df0 = df
    if story_name is not None:
        df0 = df0[df0["story"] == story_name].copy()

    df1 = filter_cases(df0, cases)

    if value_mode not in ("auto", "numeric", "label"):
        raise ValueError(
            f"[prepare_plan_dataframe] value_mode must be one of 'auto','numeric','label', got {value_mode!r}"
        )
    value_is_numeric_inferred = _is_numeric_series(df1[value_col_eff])
    if value_mode == "numeric":
        value_is_numeric = True
        label_only = False
    elif value_mode == "label":
        value_is_numeric = False
        label_only = True
    else:
        if value_col_eff in _DEFAULT_LABEL_COLS:
            value_is_numeric = False
            label_only = True
        else:
            value_is_numeric = bool(value_is_numeric_inferred)
            member_constant = (
                df1.groupby(["story", "member_id"], sort=False)[value_col_eff]
                .nunique(dropna=False)
                .le(1)
                .all()
            )
            label_only = (not value_is_numeric) or bool(member_constant)

    if cases is None:
        cases_eff = list(pd.unique(df1["output_case"]))
    else:
        cases_eff = list(cases)
    if envelope is None:
        envelope = (not label_only) and value_is_numeric and len(cases_eff) > 1
    if label_only and envelope:
        envelope = False

    if envelope:
        df2 = envelope_by_member(
            df1, value_col=value_col_eff, mode=reduction_mode, station_agg=station_agg
        )
    else:
        df2 = df1.copy()
        steps = list(pd.unique(df2["step_type"]))
        if step_type is not None:
            if step_type not in steps:
                raise ValueError(
                    f"[prepare_plan_dataframe] step_type={step_type!r} not found. Available: {steps}"
                )
            df2 = df2[df2["step_type"] == step_type].copy()
        else:
            if (not label_only) and len(steps) > 1:
                raise ValueError(
                    f"[prepare_plan_dataframe] Multiple step_type values exist for non-envelope numeric prep: {steps}. Pass step_type=... or prefilter upstream."
                )

    if label_only:
        nval = df2.groupby(["story", "member_id"], sort=False)[value_col_eff].nunique(dropna=False)
        bad_val = nval[nval > 1]
        if not bad_val.empty:
            offenders = list(bad_val.index[:8])
            raise ValueError(
                "[prepare_plan_dataframe] label-only mode requires the plotted value to be constant within each (story, member_id). "
                f"{value_col_eff!r} varies for some members. Examples (story, member_id): {offenders}."
            )
        df2s = df2.sort_values(["story", "member_id", "station"], kind="mergesort")
        df_red = (
            df2s.groupby(["story", "member_id"], sort=False, as_index=False).first().copy()
        )
        df_red = df_red.assign(
            value=df_red[value_col_eff],
            x=0.5 * (df_red["x_i"] + df_red["x_j"]),
            y=0.5 * (df_red["y_i"] + df_red["y_j"]),
        )
        keep_cols = [
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
            "x",
            "y",
            "value",
        ]
        df_red = df_red[[c for c in keep_cols if c in df_red.columns]].copy()
    else:
        df_red = reduce_plan(df2, value_col=value_col_eff, station_agg=station_agg)

    return PreparedPlan(
        df=df_red,
        value_col=value_col_eff,
        label_only=bool(label_only),
        value_is_numeric=bool(value_is_numeric),
        envelope=bool(envelope),
        cases_eff=cases_eff,
    )


