"""
Example: load a post-processed ETABS dataframe (XLSX) and plot a member-level envelope in plan.

- One figure per story found.
- Governing (Output Case, Case Type, Step Type) triple is selected per member.
- Stations are aggregated with station_agg="max" for plotting.

Adjust `value_col` to the metric you want (e.g. "DCR_M3", "DCR_MAX", etc.).
"""

import pandas as pd

from structplotlib import plot_fill_plan

# Replace with your file
path = "filtered_df.xlsx"

df_raw = pd.read_excel(path, nrows=2000)
# %%

value_col = "M3"  # <-- pick a metric column from your export

figs, ndf = plot_fill_plan(
    df_raw,
    source="sap2000",
    value_col="M3",
    cases=None,  # use all output_case values in the file
    envelope=True,  # pick governing case-triple per member
    reduction_mode="absmax",  # governing metric across cases/stations
    station_agg="max",  # aggregate duplicates at the same station
    show_values=True,
    # norm_min=0,
    # norm_max=1,
    value_fmt="{v:.2f}",
    norm_max=float(df_raw[value_col].max()),
    width_in=34,
    return_df=True,
)

# %%
# Save a quick PNG per story
for story, (fig, _ax) in figs.items():
    fig.savefig(f"plan_{story}.png", dpi=200, bbox_inches="tight")
