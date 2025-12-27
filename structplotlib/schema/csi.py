"""
structplotlib.schema.csi
========================

CSI-specific (ETABS/SAP2000) schema normalization.

Maps CSI export column names to canonical internal column names.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from .._errors import SchemaError
from .base import CANONICAL_CORE, REQUIRED_CANONICAL, ColumnSpec, require_columns

Source = Literal["etabs", "sap2000"]
Table = Literal["frame_dcr"]


def _specs_for(source: Source, table: Table) -> tuple[ColumnSpec, ...]:
    """Return ColumnSpec tuples for the given source and table."""
    if table != "frame_dcr":
        raise ValueError(f"Unknown table: {table!r}")

    if source == "etabs":
        return (
            ColumnSpec("story", "Story", ("Level",)),
            ColumnSpec("member_id", "Unique Name", ("UniqueName", "Frame")),
            ColumnSpec("station", "Station", ("Output Station", "Sta")),
            ColumnSpec("output_case", "Output Case", ("OutputCase", "Load Case")),
            ColumnSpec("case_type", "Case Type", ("CaseType",)),
            ColumnSpec("step_type", "Step Type", ("StepType",)),
            ColumnSpec("x_i", "X_I", ("XI",)),
            ColumnSpec("y_i", "Y_I", ("YI",)),
            ColumnSpec("x_j", "X_J", ("XJ",)),
            ColumnSpec("y_j", "Y_J", ("YJ",)),
            ColumnSpec("element", "Element", ("FrameElem", "Frame Elem")),
            ColumnSpec("elem_station", "Elem Station", ("ElemStation", "Elem Sta")),
        )

    if source == "sap2000":
        return (
            ColumnSpec("story", "Story", ("Level",)),
            ColumnSpec("member_id", "Frame", ("UniqueName", "Unique Name")),
            ColumnSpec("station", "Station", ("Output Station", "Sta")),
            ColumnSpec("output_case", "OutputCase", ("Load Case", "Output Case")),
            ColumnSpec("case_type", "CaseType", ("Case Type",)),
            ColumnSpec("step_type", "StepType", ("Step Type",)),
            ColumnSpec("x_i", "XI", ("X_I",)),
            ColumnSpec("y_i", "YI", ("Y_I",)),
            ColumnSpec("x_j", "XJ", ("X_J",)),
            ColumnSpec("y_j", "YJ", ("Y_J",)),
            ColumnSpec("element", "FrameElem", ("Element", "Frame Elem")),
            ColumnSpec("elem_station", "ElemStation", ("Elem Station", "Elem Sta")),
        )

    raise ValueError(f"Unknown source: {source!r}")


def resolve_canonical_name(
    input_col: str,
    *,
    source: Source,
    table: Table = "frame_dcr",
) -> str | None:
    """Resolve an input column spelling (preferred/alias/canonical) to its canonical name.

    This is useful when a caller accepts either raw ETABS/SAP headers (e.g. "My Value")
    or canonical headers (e.g. "my_value") and needs to find the canonical column name
    present after normalization.

    Returns None if the column is not part of the known schema for (source, table).
    """
    specs = _specs_for(source, table)
    for spec in specs:
        if input_col == spec.canonical:
            return spec.canonical
        if input_col == spec.preferred or input_col in spec.aliases:
            return spec.canonical
    return None


def normalize_df(
    df: pd.DataFrame,
    *,
    source: Source,
    table: Table = "frame_dcr",
    strict: bool = True,
    enforce_preferred_input_names: bool = False,
) -> pd.DataFrame:
    """
    Normalize an already-loaded dataframe to canonical columns.

    - If the dataframe already has the canonical required columns, it is validated and returned.
    - Otherwise, the dataframe is renamed based on (source, table) specs.
    - With strict=True, the function will *fail loudly* on missing/ambiguous schema.
      It does NOT require exact upstream spellings (e.g., it will accept "UniqueName" as an
      unambiguous alias for "Unique Name").
    - To enforce exact upstream spellings, set enforce_preferred_input_names=True.
    """
    df = df.copy()

    # Already canonical-ish? (allow missing story/step_type; they are defaulted here)
    if all(c in df.columns for c in CANONICAL_CORE):
        if "story" not in df.columns:
            if source == "etabs" and strict:
                raise SchemaError(
                    "[normalize_df] ETABS input is missing 'Story'. "
                    "ETABS plots are grouped per-story; ensure your export includes the 'Story' column."
                )
            df["story"] = "ALL"
        if "step_type" not in df.columns:
            df["step_type"] = ""
        require_columns(df, REQUIRED_CANONICAL, where="normalize_df(canonical)")
        return _coerce_types(df)

    specs = _specs_for(source, table)
    cols = list(df.columns)

    rename: dict[str, str] = {}
    for spec in specs:
        picked = spec.pick(
            cols,
            strict=strict,
            where=f"normalize_df({source}/{table})",
            enforce_preferred_input_names=enforce_preferred_input_names,
        )
        if picked is not None:
            rename[picked] = spec.canonical

    df = df.rename(columns=rename)

    # Default optional-but-required-for-internal-use fields
    if "story" not in df.columns:
        if source == "etabs" and strict:
            raise SchemaError(
                "[normalize_df] ETABS input is missing 'Story'. "
                "ETABS plots are grouped per-story; ensure your export includes the 'Story' column."
            )
        df["story"] = "ALL"
    if "step_type" not in df.columns:
        df["step_type"] = ""

    # Validate required canonical
    require_columns(df, REQUIRED_CANONICAL, where=f"normalize_df({source}/{table})")

    return _coerce_types(df)


def load_df(
    path: str | Path,
    *,
    source: Source,
    table: Table = "frame_dcr",
    strict: bool = True,
    enforce_preferred_input_names: bool = False,
    **read_kwargs,
) -> pd.DataFrame:
    """
    Load a CSV/XLSX file and normalize it to canonical columns.

    Parameters
    ----------
    path:
        CSV or Excel file path.
    source:
        "etabs" or "sap2000".
    table:
        Currently only "frame_dcr" (station-level DCR / design ratios).
    strict:
        Fail loudly on missing or ambiguous schema.
        (Does not require exact upstream spellings.)
    enforce_preferred_input_names:
        If True, require the preferred input spellings for the given source (e.g., ETABS "Unique Name")
        and raise if only an alias (e.g., "UniqueName") is present.
    read_kwargs:
        Passed through to pandas read function (read_csv/read_excel). Useful for skiprows, sheet_name, etc.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    if path.suffix.lower() in {".csv", ".txt"}:
        df = pd.read_csv(path, **read_kwargs)
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path, **read_kwargs)
    else:
        raise ValueError(
            f"Unsupported file type: {path.suffix!r} (expected .csv or .xlsx)"
        )

    return normalize_df(
        df,
        source=source,
        table=table,
        strict=strict,
        enforce_preferred_input_names=enforce_preferred_input_names,
    )


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Coerce key numeric columns; raises if non-numeric values are encountered.
    """
    out = df.copy()

    # numeric
    for c in ("station", "x_i", "y_i", "x_j", "y_j"):
        out[c] = pd.to_numeric(out[c], errors="raise")

    # optional numeric
    if "elem_station" in out.columns:
        out["elem_station"] = pd.to_numeric(out["elem_station"], errors="raise")

    # strings
    for c in ("story", "member_id", "output_case", "case_type", "step_type"):
        out[c] = out[c].astype(str)

    if "element" in out.columns:
        out["element"] = out["element"].astype(str)

    return out
