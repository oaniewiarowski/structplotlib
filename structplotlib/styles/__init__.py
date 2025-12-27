"""
structplotlib.styles
===================

Style defaults and normalization helpers.

- defaults: Firm defaults for fonts, annotation style, linewidths, etc.
- norms: Normalization helpers (vmin/vmax, abs norms)
"""
from .defaults import (
    DEFAULT_FONTSIZE,
    DEFAULT_K_PER_SEGMENT,
    DEFAULT_LABEL_SHIFT,
    DEFAULT_LINEWIDTH_CONTEXT,
    DEFAULT_MARKER_SIZE,
    DEFAULT_VALUE_FMT,
    DEFAULT_WATERMARK_LOC,
    DEFAULT_WIDTH_IN,
)

__all__ = [
    "DEFAULT_LINEWIDTH_CONTEXT",
    "DEFAULT_MARKER_SIZE",
    "DEFAULT_VALUE_FMT",
    "DEFAULT_WATERMARK_LOC",
    "DEFAULT_FONTSIZE",
    "DEFAULT_LABEL_SHIFT",
    "DEFAULT_K_PER_SEGMENT",
    "DEFAULT_WIDTH_IN",
]
