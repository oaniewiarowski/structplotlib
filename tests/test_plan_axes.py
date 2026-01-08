import matplotlib

matplotlib.use("Agg")  # headless backend for CI

import pandas as pd

from structplotlib import envelope_by_member, load_df, reduce_plan
from structplotlib.plots.plan_axes import (
    plan_annotate,
    plan_colorbar,
    plan_fill,
    plan_lines,
    plan_show_values,
)


def _reduced_numeric_df():
    df = load_df("tests/data/etabs_min.csv", source="etabs", strict=True)
    env = envelope_by_member(df, value_col="DCR_MAX", mode="max")
    red = reduce_plan(env, value_col="DCR_MAX", station_agg="max")
    return red


def test_plan_lines_adds_lines_not_collections():
    red = _reduced_numeric_df()
    story = str(red["story"].iloc[0])
    df_story = red[red["story"] == story].copy()

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    lines = plan_lines(df_story, ax=ax, color="black", linewidth=1.0)
    assert len(lines) > 0
    assert len(ax.lines) == len(lines)
    assert len(ax.collections) == 0
    plt.close(fig)


def test_plan_fill_returns_mappable_and_colorbar_works():
    red = _reduced_numeric_df()
    story = str(red["story"].iloc[0])
    df_story = red[red["story"] == story].copy()

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    m = plan_fill(
        df_story,
        ax=ax,
        value="value",
        cmap="turbo",
        k_per_segment=1,
        s=10,
    )
    assert len(ax.collections) == 1
    cb = plan_colorbar(m, ax=ax, label="value")
    assert cb is not None
    plt.close(fig)


def test_plan_show_values_adds_texts_and_threshold_filters():
    red = _reduced_numeric_df()
    story = str(red["story"].iloc[0])
    df_story = red[red["story"] == story].copy()

    # choose a threshold that leaves only one member
    ctrl = (
        df_story.assign(abs_v=df_story["value"].abs())
        .sort_values(["member_id", "abs_v"], ascending=[True, False], kind="mergesort")
        .groupby("member_id", sort=False)
        .first()
    )
    abs_vals = sorted([float(abs(v)) for v in ctrl["value"].to_list()])
    thresh = 0.5 * (abs_vals[0] + abs_vals[-1])

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    texts = plan_show_values(
        df_story,
        ax=ax,
        value="value",
        threshold=float(thresh),
        value_fmt="{v:.2f}",
        color="red",
        fontsize=10,
    )
    assert len(texts) == 1
    assert texts[0].get_color() == "red"
    plt.close(fig)


def test_plan_annotate_column_label_midpoints():
    df = pd.DataFrame(
        {
            "member_id": ["A", "B"],
            "x_i": [0.0, 0.0],
            "y_i": [0.0, 5.0],
            "x_j": [10.0, 10.0],
            "y_j": [0.0, 5.0],
            "label": ["foo", "bar"],
        }
    )
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    texts = plan_annotate(df, ax=ax, text="label", where="midpoint", fontsize=9)
    assert [t.get_text() for t in texts] == ["foo", "bar"]
    plt.close(fig)
