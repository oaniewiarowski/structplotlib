"""
Example: load a post-processed ETABS dataframe (XLSX) and plot a member-level envelope in plan.

- One figure per story found.
- Governing (Output Case, Case Type, Step Type) triple is selected per member.
- Stations are aggregated with station_agg="max" for plotting.

Adjust `value_col` to the metric you want (e.g. "DCR_M3", "DCR_MAX", etc.).
"""

import pandas as pd

from structplotlib import planplot
from structplotlib.plots.plan_fill_primitives import prepare_plan_dataframe

# Replace with your file
path = "filtered_df.xlsx"

df_raw = pd.read_excel(path, nrows=20_000)
# %%

value_col = "M3"  # <-- pick a metric column from your export

figs = planplot(
    df_raw,
    source="sap2000",
    value=value_col,
    cases=None,  # use all output_case values in the file
    envelope=True,  # pick governing case-triple per member
    reduction_mode="absmax",  # governing metric across cases/stations
    station_agg="max",  # aggregate duplicates at the same station
    show_values=True,
    # vmin=0,
    # vmax=1,
    value_fmt="{v:.2f}",
    vmax=float(df_raw[value_col].max()),
    width_in=34,
)

# Optional: get the exact reduced dataframe used for plotting (for debugging / verification)
prep = prepare_plan_dataframe(
    df_raw,
    source="sap2000",
    normalize=True,
    value_col=value_col,
    cases=None,
    envelope=True,
    reduction_mode="absmax",
    station_agg="max",
)
ndf = {
    st: prep.df[prep.df["story"] == st].reset_index(drop=True) for st in prep.df["story"].unique()
}

# %%
# Save a quick PNG per story
for story, (fig, _ax) in figs.items():
    fig.savefig(f"plan_{story}.png", dpi=200, bbox_inches="tight")
