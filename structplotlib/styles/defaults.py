"""
structplotlib.styles.defaults
============================

Firm defaults for plotting style constants.

These are used throughout the plotting functions unless overridden.
"""

# Line widths
DEFAULT_LINEWIDTH_CONTEXT: float = 0.5  # for unselected frame members

# Marker properties
DEFAULT_MARKER_SIZE: float = 36.0
DEFAULT_K_PER_SEGMENT: int = 5  # number of squares per frame member segment

# Annotation defaults
DEFAULT_VALUE_FMT: str = "{v:.2f}"
DEFAULT_FONTSIZE: float = 14.0
DEFAULT_LABEL_SHIFT: float = 1.5  # shifts annotation label from member midpoint

# Figure defaults
DEFAULT_WIDTH_IN: float = 14.0

# Watermark defaults
DEFAULT_WATERMARK_LOC: tuple[float, float] = (0.99, 0.01)  # (x, y) in axes coordinates

