# structplotlib — Codex Context

This document is the **authoritative context/spec** for the `structplotlib` package. Share it with Codex (or any coding agent) before asking it to implement new features.

---

## What is structplotlib?

`structplotlib` is a **small, strict, well-tested plotting library** for structural engineering workflows.

It started with CSI (ETABS/SAP2000) post-processed **frame station** results, but the long-term vision is to become a **firmwide plotting toolkit**: consistent plots, consistent styling, strict validation, and reproducible/inspectable reductions.

The package is designed around three separated layers:

1) **Schema normalization** (vendor/export-specific → canonical columns)  
2) **Reduction / envelope logic** (pure dataframe operations)  
3) **Plotting** (matplotlib only for now; no hidden business logic)

The key design goal is a clean matplotlib/pandas/numpy interface, performant and accurate plotting, and complete visibility into internal operations if desired.

---

## Repository structure (current)

```
structplotlib/
  __init__.py
  _errors.py
  _util.py

  schema/
    __init__.py
    base.py          # source-agnostic ColumnSpec + validation helpers
    csi.py           # ETABS/SAP2000 mappings → canonical schema

  reduce/
    __init__.py
    frame_stations.py  # filter/envelope/aggregate/reduce station-level **frame** data

  plots/
    __init__.py
    plan_axes.py     # Axes-level helpers for ETABS-style plan "fill diagram" (fill/lines/labels)

  styles/
    __init__.py
    defaults.py      # firmwide/project defaults (linewidths, marker sizes, fmt, etc.)
    norms.py         # helpers for vmin/vmax (including abs norms)
```

Tests live under `tests/` and use tiny deterministic CSV fixtures. To be expanded. 

---

## Public API (stable surface)

Exported from `structplotlib/__init__.py`:

### Schema
- `normalize_df(df, source="etabs"|"sap2000", table="frame_dcr", strict=True, enforce_preferred_input_names=False) -> df_canonical`
- `load_df(path, source=..., table=..., ...) -> df_canonical`
- `SchemaError`

### Reduction
- `filter_cases(df, cases: list[str]|None) -> df`
- `envelope_by_member(df, value_col=..., mode="absmax"|"max"|"min", station_agg="max"|"min"|"mean") -> df`
- `reduce_plan(df, value_col=..., station_agg=...) -> df_reduced`
- `Agg`, `Mode`

### Plotting
- `planplot(data, ...) -> (fig, ax) | {story: (fig, ax)}`  *(pipeline-friendly wrapper)*
- Axes-level helpers (matplotlib-composable):
  - `plan_lines(data, ...) -> list[Line2D]`
  - `plan_fill(data, ...) -> PathCollection`
  - `plan_show_values(data, ...) -> list[Text]`
  - `plan_annotate(data, ...) -> list[Text]`
  - `plan_colorbar(mappable, ...) -> Colorbar`

---

## Guiding principles / invariants

### Strictness + loud failures
- All public functions validate required inputs and **fail loudly** with actionable errors.
- Schema normalization accepts **unambiguous aliases** (e.g., `UniqueName` vs `Unique Name`) even in `strict=True` mode.
- Set `enforce_preferred_input_names=True` to require exact upstream spellings.

### One internal naming convention
Internally we use a canonical snake_case schema (see below). Anything vendor-specific stays at the boundary in `schema/`.

### No business logic in plotting
`plots/` functions must not silently filter/envelope. They should plot exactly what they’re given.

### Deterministic reduction
All reductions use explicit groupby aggregation (never `drop_duplicates`) and stable sorts (`mergesort`) where deterministic output matters.

---

## Canonical schema (CSI frame station plots)

Canonical columns required throughout the package:

- `story` *(string; may be `"ALL"` for SAP or for story-less data)*: Story/level identifier used for grouping plots.
- `member_id` *(string; ETABS “Unique Name” / SAP “Frame”)*: Physical frame/member identifier.
- `station` *(float)*: **Global station** — distance along the *entire frame/member* measured from the I-end in model length units.
- `output_case` *(string)*: Output/load case name (or combination name).
- `case_type` *(string)*: Case type label (e.g., `LinStatic`, `Combination`).
- `step_type` *(string; missing allowed → normalized to `""`)*: Step/result type label (e.g., `Max`, `Min`, `Step`).
- plan geometry endpoints *(float)*:
  - `x_i`, `y_i`, `x_j`, `y_j`: Member endpoints in plan used for drawing and station-to-plan interpolation.

Optional (recommended for certain exports / debugging; **required for numeric densification when `k_per_segment>1`**):
- `element` *(string)*: Finite element identifier within a frame (e.g., `109-2`). Used to preserve meaningful duplicate global stations at element boundaries.
- `elem_station` *(float)*: **Element-local station** — distance along the *finite element only*. Resets to 0 at the start of each element and increases to the element length.

**Do not confuse** `station` vs `elem_station`:
- `station` is along the whole frame/member (global).
- `elem_station` is along an individual FE segment (local) and resets at each element boundary.

**Important:** Value columns (DCR, forces, etc.) are **not part of the schema**. They should pass through unchanged; the caller always specifies `value_col=...`.  
Avoid hard-coding things like `DCR_MAX` (it’s not a CSI-native column).

---

## CSI schema mapping (ETABS vs SAP2000) - currently supports plotting of frame elements only. 

Normalization is handled in `structplotlib/schema/csi.py` using `ColumnSpec(canonical, preferred, aliases)`.

### ETABS (preferred → aliases)
- `story` ← `"Story"` (alias `"Level"`)
- `member_id` ← `"Unique Name"` (aliases `"UniqueName"`, `"Frame"`)
- `station` ← `"Station"` (aliases `"Output Station"`, `"Sta"`)
- `output_case` ← `"Output Case"` (aliases `"OutputCase"`, `"Load Case"`)
- `case_type` ← `"Case Type"` (alias `"CaseType"`)
- `step_type` ← `"Step Type"` (alias `"StepType"`)
- `x_i` ← `"X_I"` (alias `"XI"`)
- `y_i` ← `"Y_I"` (alias `"YI"`)
- `x_j` ← `"X_J"` (alias `"XJ"`)
- `y_j` ← `"Y_J"` (alias `"YJ"`)
- `element` ← `"Element"` (aliases `"FrameElem"`, `"Frame Elem"`)
- `elem_station` ← `"Elem Station"` (aliases `"ElemStation"`, `"Elem Sta"`)

### SAP2000 (preferred → aliases)
- `story` ← `"Story"` (alias `"Level"`) *(often missing; if missing downstream plot wrapper uses `"ALL"`)*
- `member_id` ← `"Frame"` (aliases `"UniqueName"`, `"Unique Name"`)
- `station` ← `"Station"` (aliases `"Output Station"`, `"Sta"`)
- `output_case` ← `"OutputCase"` (aliases `"Load Case"`, `"Output Case"`)
- `case_type` ← `"CaseType"` (alias `"Case Type"`)
- `step_type` ← `"StepType"` (alias `"Step Type"`)
- endpoints: `"XI","YI","XJ","YJ"` (aliases `"X_I","Y_I","X_J","Y_J"`)
- `element` / `elem_station` similar to above

---

## Reduction semantics (frame stations) - may require modifications for other plot types

### filter_cases(df, cases)
- If `cases` is provided, restrict to `output_case in cases`.
- If any requested cases are missing: error listing missing + available.

### station duplicates
CSI exports may contain multiple rows per `(member_id, station, case triple)` due to element breakdown or repeated lines.
- Duplicates are always aggregated per station **within a case triple** (default aggregation is configurable).

### envelope_by_member(df, value_col, mode, station_agg)
Select one governing case triple per member:
- `mode="max"`: governing triple has largest station-maximum
- `mode="min"`: governing triple has smallest station-minimum
- `mode="absmax"`: governing triple has largest `max(abs(value))`

The function returns **all station rows from that governing triple** for each member.

#### Story handling in envelope selection
`envelope_by_member` groups by `member_id` (not by story). This is correct **only if `member_id` is globally unique**.
To preserve strictness, the implementation **raises** if a single `member_id` appears on multiple stories.

### reduce_plan(df, value_col, station_agg)
Produces plot-ready data with:
- one value per `(story, member_id, station)` after enforcing “only one case triple per member” remains
- geometry endpoints retained
- adds optional `x,y` centerpoint convenience columns

**Important:** `reduce_plan` will fail loudly if multiple case triples remain per member. Use `filter_cases` and/or `envelope_by_member` first.

---

## Plotting semantics (plan fill diagram)

### planplot(data, ...)
This is the pipeline-friendly wrapper used in notebooks/pipelines.

Key behavior:
- `normalize=True` by default:
  - if df is already canonical-ish, no `source` required
  - if not canonical-ish, requires `source="etabs"` or `"sap2000"`
- Adds defaults if missing:
  - if no `story` → `story="ALL"`
  - if no `step_type` → `step_type=""`
- Optional `cases=[...]` filters by output_case
- Envelope behavior:
  - if `envelope is None`, defaults to `True` when `len(cases) > 1`
  - if envelope is True, uses `envelope_by_member`
- `frame_filter` (boolean list/Series matching df length):
  - True → selected (colored squares)
  - False → thin black context line
  - must be constant within each `(story, member_id)` or error
- Returns:
  - if `story` is provided: `(fig, ax)`
  - if `story is None`: `{story: (fig, ax)}`

---

## Styling / defaults

`structplotlib/styles/defaults.py` defines the current firm/project defaults:
- context line width
- marker size
- k_per_segment default
- annotation formatting defaults
- figure default width
- watermark location

`structplotlib/styles/norms.py` provides helpers to infer `(vmin, vmax)` (optionally in abs-space).

Plots should use these defaults unless the user overrides via kwargs.

---

## Development workflow

### Run tests
```bash
pytest -q
```

### Code quality (required before submitting a PR)
Run formatting + linting from the repo root:

```bash
black .
ruff check .
```

If you use auto-fix, re-run the check to confirm a clean result:

```bash
ruff check . --fix
ruff check .
```

Tests are small and deterministic. Fixtures are CSV under `tests/data/`.

### Add a regression test for every bug
When a real-world dataset reveals a bug:
1) Add a minimal fixture row set that reproduces it
2) Add a test that fails before the fix
3) Fix code
4) Keep the test forever

---

## Common pitfalls / known limitations

1) **Station units must be length**  
The plotting logic assumes `station` is a distance from I-end.
If you pass normalized 0–1 “output station” values, marker placement will be wrong.
(If needed later: add `station_units="length"|"normalized"` with strict checks.)

2) **Sloped members**  
Marker placement uses plan-projected line endpoints; if a member is significantly sloped in Z, station spacing in plan is approximate. Plotting of elevations is not supported. 

3) **Member_id uniqueness**  
Envelope selection assumes `member_id` is globally unique. If it appears on multiple stories, the code raises.

4) **Envelope is member-level, not station-level**  
A single governing case triple is chosen per member; stations are not allowed to switch cases.

---

## How to add new features (the “firmwide” way)

### Add a new plot type
1) Decide the **canonical reduced dataframe contract** for the plot
2) Add reducer(s) in `reduce/` (pure pandas)
3) Add plotter(s) in `plots/` (matplotlib only)
4) Add a pipeline wrapper if needed (similar to `planplot`)
5) Add tests + minimal fixtures

### Add another vendor schema
1) Create `schema/<vendor>.py`:
   - define ColumnSpec mappings
   - implement `normalize_df` wrapper
2) Keep vendor logic out of reduce/plots
3) Add tests using a tiny vendor fixture

### Add firm styling
Add constants to `styles/defaults.py` and use them in plotters (with kwargs to override).

---

## Prompt templates for Codex (copy/paste)

### Template A — Add a new plot with strict reducer separation
> Implement a new plot `plots/<name>.py` and reducer `reduce/<name>.py`.  
> Requirements: reducer must be pure pandas and fail loudly on schema errors; plot must accept reduced canonical data only; add tests and minimal fixtures; expose via `structplotlib/__init__.py`.

### Template B — Extend CSI normalization for a new export table
> Add support for a new CSI table `<table_name>`.  
> Define canonical columns, extend `schema/csi.py` with specs and table enum, add tests that validate strict normalization + alias handling, ensure existing API unchanged.

### Template C — Add a new envelope mode
> Add a new envelope selection mode `<mode>` to `envelope_by_member`.  
> Define exact scoring rule; update type hints; add tests for tie-breaking and deterministic behavior; keep strict error behavior.

### Template D — Add station unit validation
> Add `station_units="length"|"normalized"` support to `prepare_plan_dataframe` and/or `normalize_df`.  
> Default "length". Fail loudly if values look normalized but units="length" and vice versa. Add tests that cover both.

---

## “Do not break” list (hard constraints)

- Do not move filtering/enveloping logic into axes-level plotters.
- Do not hard-code any CSI value column names (DCR/ratio columns must pass through).
- Keep `planplot` returning `{story: (fig, ax)}` when `story is None`.
- Keep strict + loud validation on schema and reduction assumptions.
- Keep tests fast, deterministic, and fixture-based.
