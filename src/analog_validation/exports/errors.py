"""Stable failures for result serialization and local file access."""

from analog_validation.errors import AnalogValidationError


class ResultExportError(AnalogValidationError):
    """Base class for expected result-export failures."""


class ResultExportFormatError(ResultExportError):
    """Serialized result content violates its declared format."""


class ResultExportLimitError(ResultExportError):
    """Serialized result content exceeds a bounded resource limit."""


class ResultExportPathError(ResultExportError):
    """A result path is missing, invalid, or cannot be accessed safely."""


class ResultExportExistsError(ResultExportPathError):
    """A destination exists while overwrite permission is false."""


class UnsupportedResultExportVersion(ResultExportFormatError):
    """Serialized result content declares an unsupported schema version."""


__all__ = [
    "ResultExportError",
    "ResultExportExistsError",
    "ResultExportFormatError",
    "ResultExportLimitError",
    "ResultExportPathError",
    "UnsupportedResultExportVersion",
]
