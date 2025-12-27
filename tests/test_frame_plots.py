import matplotlib

matplotlib.use("Agg")  # headless backend for CI

import pandas as pd
import pytest

from structplotlib import (
    SchemaError,
    envelope_by_member,
    load_df,
    plot_fill_plan,
    plot_plan,
    reduce_plan,
)


def test_schema_normalize_etabs_required_canonical_columns_exist():
    """ETABS-like input normalizes to the canonical geometry/case columns.

    Value columns are *not* part of the canonical schema; they should pass through unchanged.
    """
    df = load_df("tests/data/etabs_min.csv", source="etabs", strict=True)
    for c in (
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
    ):
        assert c in df.columns
    assert set(df["member_id"].unique()) == {"A1", "B1"}
    # The test fixture uses a synthetic value column; it should remain available.
    assert "DCR_MAX" in df.columns


def test_schema_normalize_etabs_accepts_stripped_space_aliases():
    # Many pipelines strip spaces from CSI export headers (e.g. "UniqueName", "OutputCase").
    # Strict mode should still work as long as the mapping is unambiguous.
    df = load_df("tests/data/etabs_min_alias.csv", source="etabs", strict=True)
    assert set(df["member_id"].unique()) == {"A1", "B1"}
    assert set(df["output_case"].unique()) == {"CASE_A", "CASE_B"}
    assert "DCR_MAX" in df.columns


def test_schema_normalize_sap_missing_story_and_step_type_are_defaulted():
    """SAP-like fixtures often omit Story and StepType columns.

    The schema layer should default:
    - story -> "ALL"
    - step_type -> ""
    """
    df = load_df("tests/data/sap_min.csv", source="sap2000", strict=True)
    for c in (
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
    ):
        assert c in df.columns
    assert set(df["member_id"].unique()) == {"A1", "B1"}
    assert set(df["story"].unique()) == {"ALL"}
    assert set(df["step_type"].unique()) == {""}
    # Value column passes through unchanged (fixture uses "DCR Max")
    assert "DCR Max" in df.columns


def test_schema_missing_cols_loud():
    with pytest.raises(SchemaError) as e:
        load_df("tests/data/bad_missing_cols.csv", source="etabs", strict=True)
    msg = str(e.value)
    assert "Missing required columns" in msg
    assert "Output Case" in msg or "output_case" in msg


def test_envelope_by_member_picks_controlling_case():
    df = load_df("tests/data/etabs_min.csv", source="etabs", strict=True)
    # use the fixture's synthetic value column explicitly
    env = envelope_by_member(df, value_col="DCR_MAX", mode="max")

    a = env[env["member_id"] == "A1"]
    b = env[env["member_id"] == "B1"]

    assert set(a["output_case"].unique()) == {
        "CASE_B"
    }  # member A1 should envelope to CASE_B (max=1.2)
    assert set(b["output_case"].unique()) == {"CASE_A"}  # member B1 only has CASE_A


def test_reduce_plan_station_aggregation_is_groupby_max():
    df = load_df("tests/data/etabs_min.csv", source="etabs", strict=True)
    env = envelope_by_member(df, value_col="DCR_MAX", mode="max")
    red = reduce_plan(env, value_col="DCR_MAX", station_agg="max")

    # Member A1 station 5.0 in CASE_B has duplicates (1.20 and 1.15); max should be 1.20
    a5 = red[(red["member_id"] == "A1") & (red["station"] == 5.0)]
    assert len(a5) == 1
    assert abs(float(a5.iloc[0]["value"]) - 1.2) < 1e-12


def test_plot_smoke_and_annotation_matches_value():
    df = load_df("tests/data/etabs_min.csv", source="etabs", strict=True)
    env = envelope_by_member(df, value_col="DCR_MAX", mode="max")
    red = reduce_plan(env, value_col="DCR_MAX", station_agg="max")

    fig, ax = plot_plan(
        red,
        story="L1",
        show_values=True,
        value_fmt="{v:.2f}",
        value_col="value",
        show_colorbar=False,
    )
    texts = [t.get_text() for t in ax.texts]
    assert "1.20" in texts  # member A1 controlling station label
    assert "0.50" in texts  # member B1 controlling station label

    import matplotlib.pyplot as plt

    plt.close(fig)


def test_plot_annotation_alt_color_above_threshold():
    df = load_df("tests/data/etabs_min.csv", source="etabs", strict=True)
    env = envelope_by_member(df, value_col="DCR_MAX", mode="max")
    red = reduce_plan(env, value_col="DCR_MAX", station_agg="max")

    fig, ax = plot_plan(
        red,
        story="L1",
        show_values=True,
        value_fmt="{v:.2f}",
        value_col="value",
        show_colorbar=False,
        annotate_threshold=1.0,
        value_text_color="black",
        value_text_color_above_threshold="red",
    )

    # Threshold=1.0 filters out member B1's 0.50 label, leaving only A1's 1.20 label.
    assert [t.get_text() for t in ax.texts] == ["1.20"]
    assert ax.texts[0].get_color() == "red"

    import matplotlib.pyplot as plt

    plt.close(fig)


def test_plot_fill_plan_normalize_accepts_alias_headers_and_raw_value_column():
    # Simulate common pipeline-altered ETABS headers with stripped spaces
    raw = pd.read_csv("tests/data/etabs_min.csv")
    raw = raw.rename(
        columns={
            "Unique Name": "UniqueName",
            "Output Case": "OutputCase",
            "Case Type": "CaseType",
            "Step Type": "StepType",
        }
    )

    figs = plot_fill_plan(
        raw,
        source="etabs",
        normalize=True,
        value_col="DCR_MAX",  # value column is not part of schema; should pass through
        cases=["CASE_A", "CASE_B"],
        envelope=True,
        reduction_mode="max",
        show_colorbar=False,
        show_values=False,
        width_in=6.0,
    )
    assert "L1" in figs

    # Clean up created figures
    for fig, _ax in figs.values():
        fig.clf()
        import matplotlib.pyplot as plt

        plt.close(fig)


def test_plot_fill_plan_return_df_includes_output_case_for_debugging():
    raw = pd.read_csv("tests/data/etabs_min.csv")
    figs, dfs = plot_fill_plan(
        raw,
        source="etabs",
        normalize=True,
        value_col="DCR_MAX",
        cases=["CASE_A", "CASE_B"],
        envelope=True,
        reduction_mode="max",
        show_colorbar=False,
        show_values=False,
        width_in=6.0,
        return_df=True,
    )

    assert "L1" in figs
    assert "L1" in dfs
    df_used = dfs["L1"]
    assert "output_case" in df_used.columns

    # Matches envelope fixture expectations:
    # - member A1 envelopes to CASE_B (max=1.2)
    # - member B1 only has CASE_A
    assert set(df_used[df_used["member_id"] == "A1"]["output_case"].unique()) == {"CASE_B"}
    assert set(df_used[df_used["member_id"] == "B1"]["output_case"].unique()) == {"CASE_A"}

    # Clean up created figures
    for fig, _ax in figs.values():
        fig.clf()
        import matplotlib.pyplot as plt

        plt.close(fig)