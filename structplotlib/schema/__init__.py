"""
structplotlib.schema
====================

Schema normalization and validation.

- base: Generic column validation and canonicalization helpers
- csi: CSI-specific (ETABS/SAP2000) mappings and normalization
"""
from .base import (
    require_columns,
    ColumnSpec,
    REQUIRED_CANONICAL,
    CANONICAL_CORE,
    OPTIONAL_CANONICAL,
)
from .csi import normalize_df, load_df, resolve_canonical_name, Source, Table

__all__ = [
    "require_columns",
    "ColumnSpec",
    "REQUIRED_CANONICAL",
    "CANONICAL_CORE",
    "OPTIONAL_CANONICAL",
    "normalize_df",
    "load_df",
    "resolve_canonical_name",
    "Source",
    "Table",
]

