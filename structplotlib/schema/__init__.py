"""
structplotlib.schema
====================

Schema normalization and validation.

- base: Generic column validation and canonicalization helpers
- csi: CSI-specific (ETABS/SAP2000) mappings and normalization
"""

from .base import (
    CANONICAL_CORE,
    OPTIONAL_CANONICAL,
    REQUIRED_CANONICAL,
    ColumnSpec,
    require_columns,
)
from .csi import Source, Table, load_df, normalize_df, resolve_canonical_name

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
