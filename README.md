# structplotlib

A small, strict plotting library for structural engineering dataframes — starting with **CSI (ETABS/SAP2000) frame station results**
and growing into a **firmwide plotting toolkit** (consistent plots, strict validation, reproducible reductions).

Key idea: keep a clean separation between

1. **Schema normalization** (vendor/export-specific → canonical columns)
2. **Reduction / envelope logic** (pure pandas)
3. **Plotting** (matplotlib only; no hidden business logic)

---

## Features (today)

- ETABS-style plan **“fill diagram”** look: square markers along frame members.
- **One figure per Story** when `story` exists; otherwise a single plot (keyed `"ALL"`).
- Optional **member-level envelope** across multiple cases:
  - choose one governing `(output_case, case_type, step_type)` triple per member via `min`, `max`, or `absmax`
  - plot all stations from that governing triple (no station-wise case switching)
- Optional **Show Values** labels (formatted via `value_fmt`).
- Optional **context geometry**:
  - use `frame_filter` to draw non-selected members as thin black lines
- Optional `return_df=True` returns the **exact reduced dataframe used for plotting**.

---

## Installation

```bash
pip install structplotlib
```

### From source (recommended during development)

```bash
pip install -e ".[dev]"
```

---

## Quickstart (pipeline-friendly)

`plot_fill_plan` is the main entry point for notebooks/pipelines. It can accept a **raw ETABS/SAP export** (optionally normalizing)
or an already-canonical dataframe.

```python
import pandas as pd
from structplotlib import plot_fill_plan

raw = pd.read_excel("my_etabs_export.xlsx")

figs, dfs = plot_fill_plan(
    raw,
    source="etabs",                 # required if raw/non-canonical
    normalize=True,                 # default True
    value_col="DCR_M3",          # any numeric column you want to plot
    cases=["1.2D+1.6L", "1.2D+1.0Wx+1.0L"],
    envelope=True,                  # member-level governing triple
    reduction_mode="absmax",        # default absmax
    station_agg="max",
    show_values=True,
    value_fmt="{v:.2f}",
    frame_filter=None,              # optional boolean mask aligned to raw df rows
    return_df=True,                 # returns (figs_dict, dfs_dict)
)

# Example: get the reduced df for story "L3"
df_L3 = dfs["L3"]
```

`figs` is a dict keyed by story name: `{story: (fig, ax)}`.

---

## Supported inputs

structplotlib works with **ETABS** and **SAP2000** frame station exports. The library automatically normalizes software-specific column names to a canonical schema.

### Canonical schema (CSI frame stations)

Internally, structplotlib uses canonical snake_case column names. The minimum set for CSI "frame stations" plots is:

**Required:**
- `member_id` (str)
- `station` (float; **distance from I-end** in model length units)
- `output_case` (str)
- `case_type` (str)
- `step_type` (str; optional → normalized to `""`)
- `x_i`, `y_i`, `x_j`, `y_j` (float)

**Optional** (recommended for element-breakdown exports / debugging):
- `story` (str) — if missing, the pipeline wrapper sets `"ALL"`
- `element` (str)
- `elem_station` (float)

**Value columns are not part of the schema.** Pass the column you want to plot via `value_col=...`.


---

## Strictness and alias handling

- `normalize_df(..., strict=True)` validates required columns and fails loudly with actionable errors.
- `strict=True` accepts **unambiguous aliases** (e.g., `UniqueName` vs `Unique Name`).
- To enforce exact upstream spellings, use: `enforce_preferred_input_names=True`.

---

## Core API (advanced)

If you want to build a custom pipeline (e.g., normalize once, reduce many times):

```python
from structplotlib import normalize_df, filter_cases, envelope_by_member, reduce_plan
from structplotlib.plots.plan_fill import plot_plan_by_story

df = normalize_df(raw, source="etabs", table="frame_dcr", strict=True)

df = filter_cases(df, cases=["CASE_A", "CASE_B"])
df_env = envelope_by_member(df, value_col="PMM Ratio", mode="absmax", station_agg="max")
df_red = reduce_plan(df_env, value_col="PMM Ratio", station_agg="max")

figs = plot_plan_by_story(df_red, show_values=True, value_fmt="{v:.2f}")
```

---

## Development

Run tests from the repo root:

```bash
pytest -q
```

### Code quality (required before submitting a PR)

Before opening or updating a PR, run formatting + linting from the repo root:

```bash
black .
ruff check .
```

If you use auto-fix, re-run the check to confirm a clean result:

```bash
ruff check . --fix
ruff check .
```

### Internal docs
- `CODEX_CONTEXT.md` — authoritative spec to share with coding agents
- `DESIGN_NOTES.md` — roadmap + acceptance scenarios (legacy from AGENTS.md)

---

## Reporting issues

Please report bugs, request features, or ask questions by opening an issue on the [GitHub repository](https://github.com/oaniewiarowski/structplotlib).

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
