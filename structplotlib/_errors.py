"""
structplotlib._errors
====================

Shared error classes used across the package.
"""


class SchemaError(KeyError):
    """Raised when schema normalization/validation fails."""


class ReduceError(ValueError):
    """Raised when data reduction/enveloping fails."""


class PlotError(ValueError):
    """Raised when plotting fails."""

