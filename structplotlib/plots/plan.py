"""
structplotlib.plots.plan
=======================

Seaborn-esque high-level wrappers for plan plotting.

These functions are intentionally opinionated conveniences that compose the
Matplotlib-ish primitives from `structplotlib.plots.plan_fill_primitives`.

Goals
-----
- Accept raw CSI-like dataframes (optional normalization).
- Provide a small set of semantic args (kind/value/cases/envelope/step_type/story).
- Prefer Matplotlib conventions: `data=...`, string column names, and `*_kws` passthrough.
- Return artists for post-hoc tweaking/testing.

Notes
-----
- Multi-story behavior: if `story=None`, returns a dict keyed by story.
- Selection/context: if you pass `frame_filter`, unselected members are drawn as thin black lines.
  This is a wrapper convenience (not baked into the low-level renderers).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .plan_axes import plan_annotate, plan_colorbar, plan_fill, plan_lines, plan_show_values
from .plan_fill_primitives import _infer_figsize_from_bbox, prepare_plan_dataframe


Kind = Literal["auto", "fill", "lines"]


@dataclass(frozen=True)
class PlanArtists:
    """Lightweight collection of artists produced by `planplot`.

    Keys are optional depending on mode:
    - context_lines: list[Line2D]
    - lines: list[Line2D]
    - markers: PathCollection
    - colorbar: Colorbar
    - texts: list[Text]
    """

    context_lines: list[Any] | None = None
    lines: list[Any] | None = None
    markers: Any | None = None
    colorbar: Any | None = None
    texts: list[Any] | None = None


def _normalize_label_spec(
    label: str | Sequence[str] | Callable[[pd.Series], str] | None,
) -> Callable[[pd.Series], str] | None:
    if label is None:
        return None
    if callable(label):
        return label
    if isinstance(label, str):
        return lambda r: str(r[label]) if label in r.index else str(label)
    cols = list(label)
    return lambda r: " — ".join(str(r[c]) for c in cols if c in r.index)


def _attach_member_selection_from_frame_filter(
    df_input: pd.DataFrame, df_reduced: pd.DataFrame, *, frame_filter: Sequence[bool]
) -> tuple[pd.DataFrame, str]:
    """Derive member-level selection from a row-aligned boolean mask and merge onto reduced df."""
    if len(frame_filter) != len(df_input):
        raise ValueError("[planplot] frame_filter must be the same length as the *input* dataframe")
    ff = np.asarray(list(frame_filter), dtype=bool)
    df0 = df_input.copy()
    df0["_selected_row"] = ff
    g = df0.groupby(["story", "member_id"], sort=False)["_selected_row"].nunique(dropna=False)
    bad = g[g > 1]
    if not bad.empty:
        offenders = list(bad.index[:8])
        raise ValueError(
            "[planplot] frame_filter must be constant within each (story, member_id). "
            f"Examples with mixed True/False: {offenders}"
        )
    selected_map = (
        df0.groupby(["story", "member_id"], sort=False, as_index=False)["_selected_row"]
        .first()
        .rename(columns={"_selected_row": "selected"})
    )
    out = df_reduced.merge(selected_map, on=["story", "member_id"], how="left")
    out["selected"] = out["selected"].fillna(True).astype(bool)
    return out, "selected"


def planplot(
    data: pd.DataFrame,
    *,
    kind: Kind = "auto",
    value: str | None = None,
    value_mode: Literal["auto", "numeric", "label"] = "auto",
    # schema / normalization
    source: Literal["etabs", "sap2000"] | None = None,
    table: str = "frame_dcr",
    normalize: bool = True,
    strict: bool = True,
    enforce_preferred_input_names: bool = False,
    # filtering / envelope / reduction
    cases: list[str] | None = None,
    envelope: bool | None = None,
    reduction_mode: Literal["max", "min", "absmax"] = "absmax",
    station_agg: Literal["max", "min", "mean"] = "max",
    step_type: str | None = None,
    story: str | None = None,
    # selection/context
    frame_filter: Sequence[bool] | None = None,
    # figure
    ax=None,
    width_in: float = 14.0,
    title: str | None = None,
    watermark: str | None = None,
    equal_aspect: bool = True,
    show_axes: bool = False,
    # fill semantics
    cmap: str = "turbo",
    vmin: float | None = None,
    vmax: float | None = None,
    k_per_segment: int = 5,
    marker_size: float = 36.0,
    colorbar: bool = True,
    colorbar_kws: Mapping[str, Any] | None = None,
    # annotation semantics
    label: str | Sequence[str] | Callable[[pd.Series], str] | None = None,
    label_at: Literal["midpoint"] = "midpoint",
    show_values: bool = False,
    value_fmt: str | Callable[[float], str] = "{v:.2f}",
    annotate_threshold: float | None = None,
    value_text_color: str = "black",
    value_text_color_above_threshold: str | None = None,
    label_shift: float = 1.5,
    # style passthrough
    line_kws: Mapping[str, Any] | None = None,
    context_line_kws: Mapping[str, Any] | None = None,
    fill_kws: Mapping[str, Any] | None = None,
    text_kws: Mapping[str, Any] | None = None,
    # returns
    return_artists: bool = False,
):
    """High-level plan plotting wrapper (seaborn-esque).

    Parameters
    ----------
    data:
        Raw or canonical dataframe (station-level).
    kind:
        - "auto": infer label-only vs fill after preparation
        - "fill": force numeric station markers (errors if values are non-numeric/member-constant)
        - "lines": force line-only rendering
    value:
        Column to plot. Required for "fill"; optional for "lines" (lines can be geometry-only).
        Internally, preparation produces a reduced df with canonical column "value".
    label:
        Optional per-member label(s) to annotate at midpoints.
        - str: a column name (e.g., "member_id", "output_case")
        - list[str]: combine multiple columns with " — "
        - callable(row)->str

    Returns
    -------
    If story is provided:
        (fig, ax) or (fig, ax, artists)
    If story is None:
        {story: (fig, ax)} or {story: (fig, ax, artists)}
    """
    if colorbar_kws is None:
        colorbar_kws = {}
    if line_kws is None:
        line_kws = {}
    if context_line_kws is None:
        context_line_kws = {}
    if fill_kws is None:
        fill_kws = {}
    if text_kws is None:
        text_kws = {}

    if kind not in ("auto", "fill", "lines"):
        raise ValueError(f"[planplot] kind must be 'auto'|'fill'|'lines', got {kind!r}")

    if value is None and kind in ("auto", "fill"):
        raise ValueError("[planplot] value=... is required for kind='auto' or kind='fill'")

    # Prepare (normalize/filter/envelope/reduce). This mirrors legacy correctness behavior.
    if value is None:
        # Geometry-only lines: still normalize to ensure canonical geometry columns if requested.
        # Use a harmless label-ish value to drive the reducer.
        value = "member_id"

    prep = prepare_plan_dataframe(
        data,
        source=source,
        table=table,
        normalize=normalize,
        strict=strict,
        enforce_preferred_input_names=enforce_preferred_input_names,
        value_col=value,
        value_mode=value_mode,
        cases=cases,
        envelope=envelope,
        reduction_mode=reduction_mode,  # type: ignore[arg-type]
        station_agg=station_agg,  # type: ignore[arg-type]
        step_type=step_type,
        story_name=story,
    )

    df_red = prep.df.copy()

    # Selection/context derived from input (row-aligned) mask
    selected_col = None
    if frame_filter is not None:
        df_red, selected_col = _attach_member_selection_from_frame_filter(
            data if story is None else data[data.get("story", "ALL") == story],
            df_red,
            frame_filter=frame_filter,
        )

    # Determine mode for plotting
    label_only = prep.label_only
    if kind == "lines":
        label_only = True
    elif kind == "fill":
        if prep.label_only:
            raise ValueError(
                "[planplot] kind='fill' requested but the prepared data is label-only "
                "(non-numeric or constant-per-member)."
            )
        label_only = False

    label_fn = _normalize_label_spec(label)

    def _plot_one_story(df_story: pd.DataFrame, st: str):
        # Ax creation: only when caller didn't pass ax
        if ax is None:
            fig, ax0 = plt.subplots(figsize=_infer_figsize_from_bbox(df_story, width_in=width_in))
        else:
            fig, ax0 = ax.figure, ax

        ctx_lines = None
        lines = None
        markers = None
        cb = None
        texts = []

        # Split context/selected if selection exists
        if selected_col is not None:
            df_ctx = df_story[~df_story[selected_col].astype(bool)].copy()
            df_sel = df_story[df_story[selected_col].astype(bool)].copy()
        else:
            df_ctx = df_story.iloc[0:0].copy()
            df_sel = df_story

        # Context layer (thin black lines)
        if not df_ctx.empty:
            ctx_lines = plan_lines(
                df_ctx,
                ax=ax0,
                member="member_id",
                color="black",
                linewidth=0.5,
                zorder=1,
                **dict(context_line_kws),
            )

        if label_only:
            # Selected lines
            lines = plan_lines(
                df_sel,
                ax=ax0,
                member="member_id",
                color="black",
                linewidth=1.2,
                zorder=2,
                **dict(line_kws),
            )

            # Labels: default to plotted value; override via `label=...`
            if label_fn is None:
                label_fn_eff = lambda r: str(r["value"])
            else:
                label_fn_eff = label_fn

            texts.extend(
                plan_annotate(
                    df_sel.groupby("member_id", sort=False, as_index=False).first(),
                    ax=ax0,
                    where="midpoint",
                    rotate_with_member=True,
                    text=label_fn_eff,
                    fontsize=10.0,
                    color="black",
                    **dict(text_kws),
                )
            )
        else:
            # Fill markers for selected members only (or all if none selected)
            df_fill = df_sel if not df_sel.empty else df_story
            markers = plan_fill(
                df_fill,
                ax=ax0,
                value="value",
                member="member_id",
                station="station",
                densify=("linear" if int(k_per_segment) > 1 else "none"),
                k_per_segment=int(k_per_segment),
                cmap=str(cmap),
                vmin=vmin,
                vmax=vmax,
                marker="s",
                s=float(marker_size),
                linewidths=0.0,
                alpha=0.95,
                zorder=3.0,
                **dict(fill_kws),
            )
            if colorbar:
                cb = plan_colorbar(
                    markers,
                    ax=ax0,
                    label=str(value),
                    location="bottom",
                    fraction=0.05,
                    pad=0.0,
                    aspect=10,
                    **dict(colorbar_kws),
                )

            # Optional controlling-station labels (ETABS-like "Show Values")
            if show_values:
                if annotate_threshold is not None:
                    base_color = (
                        str(value_text_color_above_threshold)
                        if value_text_color_above_threshold is not None
                        else str(value_text_color)
                    )
                else:
                    base_color = str(value_text_color)
                texts.extend(
                    plan_show_values(
                        df_fill,
                        ax=ax0,
                        value="value",
                        member="member_id",
                        station="station",
                        mode="absmax",
                        value_fmt=value_fmt,
                        threshold=annotate_threshold,
                        normal_offset=float(label_shift),
                        fontsize=12.0,
                        color=base_color,
                        **dict(text_kws),
                    )
                )

        # Axes decoration
        if equal_aspect:
            ax0.set_aspect("equal", adjustable="datalim")
        if not show_axes:
            ax0.axis("off")

        if title is None:
            ttl = f"{st} — {value}"
        else:
            ttl = str(title)
        ax0.set_title(ttl)

        if watermark:
            ax0.text(
                0.99,
                0.01,
                str(watermark),
                transform=ax0.transAxes,
                ha="right",
                va="bottom",
                fontsize=max(8.0, 0.7 * float(text_kws.get("fontsize", 12.0))),
                alpha=0.5,
                zorder=10,
            )

        if return_artists:
            return fig, ax0, PlanArtists(
                context_lines=ctx_lines,
                lines=lines,
                markers=markers,
                colorbar=cb,
                texts=texts if texts else None,
            )
        return fig, ax0

    if story is not None:
        df_story = df_red[df_red["story"] == story].copy()
        if df_story.empty:
            raise ValueError(f"[planplot] No rows for story={story!r}")
        return _plot_one_story(df_story, str(story))

    out = {}
    for st in pd.unique(df_red["story"]):
        df_story = df_red[df_red["story"] == st].copy()
        out[str(st)] = _plot_one_story(df_story, str(st))
    return out



