"""Exceptions raised by the feasibility report pipeline."""


class FeasibilityError(Exception):
    """Base class for feasibility-package errors."""


class MappingError(FeasibilityError):
    """Raised when a mapping file fails validation."""


class MissingData(FeasibilityError):
    """Raised inside a calc when an expected input is absent.

    The dispatcher catches this and substitutes the mapping's fallback,
    logging the cell in ``response.missing_fields``.
    """

