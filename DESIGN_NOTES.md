# structplotlib — Design Notes

This file contains **design notes / roadmap / test inspirations**.

**Authoritative spec:** `CODEX_CONTEXT.md` (treat that as the single source of truth for current behavior).

---

## High-level intent

`structplotlib` aims to produce **ETABS/SAP-like structural plots** from tabular post-processed data:

- ETABS-style **plan “fill diagram”** look: square markers along frame members.
- One figure per **Story** when story exists; otherwise a single plot (e.g., SAP exports without story).
- Optional **Show Values** labels at the controlling station(s).
- Optional **context geometry**: draw non-selected members as thin black lines.
- Optional **watermark** (e.g., filename, run metadata).
- **Member-level envelope** across cases: choose a governing `(output_case, case_type, step_type)` triple per member using `min`, `max`, or `absmax` scoring.
- Always be able to return the **exact reduced dataframe used to plot** for verification.
- Other plot types/classes will be added in the future.

---

## Use-case scenarios (acceptance tests / “expected user behavior”)

These scenarios represent how engineers actually use CSI results in practice. They should remain working as features grow.

### Scenario 1 — Exact case plot (single output_case)
**User wants:** plot a single output case/combination and review the distribution along members.

**Expected behavior:**
- User supplies `cases=[<one case>]`.
- Pipeline validates the case exists.
- Duplicates at the same station (e.g., element breakdown) are aggregated using `station_agg`.
- Plot shows station markers and (optionally) a single Show Values label per member.

### Scenario 2 — Exact case plot with prefiltered dataframe
**User wants:** pass in a df already filtered upstream (e.g., one story, one case) and just plot.

**Expected behavior:**
- `plot_fill_plan(df, normalize=..., envelope=False, cases=None)` works.
- Functions still validate canonical columns and loudly error if required columns are missing.
- Plotting is deterministic and labels match the plotted values.

### Scenario 3 — Plot a CSI “Min” or “Max” step type (not both)
**User wants:** for cases that include `StepType` (often `Min` / `Max`), plot just one of them.

**Expected behavior:**
- If `step_type` values include both `Min` and `Max`, user must select one (or the API provides an explicit kwarg).
- Library should **fail loudly** if both exist and the user didn’t disambiguate.
- Result is a coherent plot for the chosen step type only.

### Scenario 4 — Envelope across multiple cases (member-level governing triple)
**User wants:** provide a list of cases and get a clean envelope plot where each member is drawn from the **single governing case triple**.

**Expected behavior:**
- User supplies `cases=[...]` (multiple).
- The library selects the governing `(output_case, case_type, step_type)` triple **per member** using `mode in {min,max,absmax}`.
- The plot uses **only station rows from that governing triple** for that member.
- No silent mixing of different case triples along a single member.
- Aggregation ensures **no duplicate station rows per member** remain before plotting.

---

## Convenience wrapper (“pipeline UX”) goals

The wrapper exists to make notebook / pipeline usage frictionless while preserving correctness.

### Key wrapper responsibilities
- Optional schema normalization (`normalize=True` default).
- Filtering by `cases` (list of output_case names).
- Optional envelope selection (member-level).
- Station deduplication/aggregation.
- Per-story plotting (or single plot if no story).
- Optional `return_df=True` returning reduced dfs keyed like figs.

### Selection vs context lines
Support a `frame_filter` mask (boolean Series/list aligned to input df rows):
- `True` → member is “selected” (colored squares)
- `False` → member is “context” (thin black line)
- Must be consistent **within a member** (otherwise error).

### Value formatting
Show Values labels should accept:
- `value_fmt="{v:.2f}"` (default) or
- `value_fmt` as a callable `(v) -> str`.

---

## Known pitfalls / reminders

- **Station units:** v1 assumes `station` is **distance from I-end** (length units), not normalized 0–1.
- **Sloped members:** marker placement is in plan; heavy Z-slope can distort station spacing visually.
- **Member-id uniqueness:** envelope selection assumes `member_id` uniquely identifies an object; if the same id appears on multiple stories, prefer loud failure.

---

## Future refinement prompts (roadmap)

These are intentionally phrased as questions to guide future iterations:

1) Do we want ETABS-like **Min & Max plotted together** (two label sets / two layers)?
2) Do we want **per-story normalization** or **global normalization** across all stories (for colorbar comparability)?
3) Should `frame_filter` also accept a **list of member_ids** (instead of a row-aligned boolean mask) for convenience?
4) Should we support **curved/segmented members** (polyline geometry) vs only straight `(x_i,y_i)-(x_j,y_j)`?
5) Do we want to persist and reuse a **paths_cache** for speed in repeated plots?
6) Do we want first-class support for **station_units="length"|"normalized"** with strict validation?
7) Do we want **station-wise envelope** as an optional alternative to member-level envelope (with strong warnings about interpretation)?
8) Firm styling:
   - title blocks, legend conventions, watermark defaults
   - consistent fonts/sizes for internal deliverables
9) Extend beyond CSI:
   - additional schema modules (`schema/ram.py`, `schema/stadd.py`, etc.)
   - plot families beyond plan fill: drifts, reactions, time history, section cuts
10) Extend beyond frame plots:
   - area element plots
   - bubble plots
   - custom plan annotations (boxed-end reactions, drawing markups, etc)
   - support for elevation plots and 3D (both require Z coordinate data)
---

## How to use this file with Codex

- Treat `CODEX_CONTEXT.md` as the spec for what must work today.
- Use this file to decide what to build next and what tests to add.
- Any time a new feature is added, add at least one minimal regression fixture and a deterministic test.

