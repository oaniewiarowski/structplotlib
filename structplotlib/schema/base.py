"""
structplotlib.schema.base
========================

Generic schema validation and canonicalization helpers.

These are source-agnostic utilities for column validation and selection.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import pandas as pd

from .._errors import SchemaError
from .._util import _did_you_mean


def require_columns(df: pd.DataFrame, required: Iterable[str], *, where: str) -> None:
    """Validate that required columns are present in the dataframe.

    Raises SchemaError with helpful hints if columns are missing.
    """
    required = list(required)
    missing = [c for c in required if c not in df.columns]
    if not missing:
        return

    cols = list(df.columns)
    hints: list[str] = []
    for m in missing:
        hits = _did_you_mean(cols, m)
        if hits:
            hints.append(
                f"Expected {m!r} but found {hits!r} (looks like spaces/underscores/case were changed upstream)."
            )

    msg = (
        f"[{where}] Missing required columns: {missing}\n"
        f"Available columns (first 30): {cols[:30]}" + (" ..." if len(cols) > 30 else "")
    )
    if hints:
        msg += "\nHints:\n- " + "\n- ".join(hints)
    raise SchemaError(msg)


@dataclass(frozen=True)
class ColumnSpec:
    """Specification for mapping input column names to canonical names.

    Attributes
    ----------
    canonical:
        The canonical (internal) column name (snake_case).
    preferred:
        The preferred input column name for the source.
    aliases:
        Alternative input column names that map to the same canonical name.
    """

    canonical: str
    preferred: str
    aliases: tuple[str, ...] = ()

    def pick(
        self,
        cols: Sequence[str],
        *,
        strict: bool,
        where: str,
        enforce_preferred_input_names: bool = False,
    ) -> str | None:
        """Return the chosen existing input column name, or None if none exist.

        Parameters
        ----------
        cols:
            Available column names in the input dataframe.
        strict:
            If True, fail loudly on ambiguous or missing columns.
            Does NOT require exact upstream spellings by default.
        where:
            Context string for error messages.
        enforce_preferred_input_names:
            If True and strict=True, require the preferred input spelling
            and raise if only an alias is present.

        Returns
        -------
        The chosen column name from cols, or None if not found.
        """
        preferred_present = self.preferred in cols
        alias_present = [a for a in self.aliases if a in cols]

        # "strict" means: fail loudly on missing/ambiguous schema, but do NOT require that the
        # upstream column spellings exactly match our preferred variants. Real CSI exports and
        # user pipelines often strip spaces (e.g., "UniqueName"), and that's still unambiguous.
        #
        # If you want to enforce upstream spellings ("Unique Name" only), set
        # enforce_preferred_input_names=True.
        if strict:
            if preferred_present and alias_present:
                raise SchemaError(
                    f"[{where}] Found both preferred {self.preferred!r} and aliases {alias_present!r} for canonical {self.canonical!r}. "
                    "Provide only one naming convention upstream."
                )
            if enforce_preferred_input_names and (not preferred_present) and alias_present:
                raise SchemaError(
                    f"[{where}] Expected preferred input column {self.preferred!r} for canonical {self.canonical!r}, but found alias {alias_present!r}. "
                    "Rename upstream or call load_df(..., enforce_preferred_input_names=False)."
                )

            # Accept preferred if present, else accept a single alias.
            if preferred_present:
                return self.preferred
            if len(alias_present) > 1:
                raise SchemaError(
                    f"[{where}] Ambiguous aliases for canonical {self.canonical!r}: {alias_present!r}. Provide only one of these."
                )
            return alias_present[0] if alias_present else None

        # non-strict: accept preferred or any alias, but still forbid ambiguity
        candidates = []
        if preferred_present:
            candidates.append(self.preferred)
        candidates.extend(alias_present)
        if len(candidates) > 1:
            raise SchemaError(
                f"[{where}] Ambiguous input columns for canonical {self.canonical!r}: {candidates!r}. Provide only one of these."
            )
        return candidates[0] if candidates else None


# Canonical columns used throughout the package
REQUIRED_CANONICAL = (
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
)

CANONICAL_CORE = tuple(
    c for c in REQUIRED_CANONICAL if c not in ("story", "step_type")
)

OPTIONAL_CANONICAL = (
    "element",
    "elem_station",
)

