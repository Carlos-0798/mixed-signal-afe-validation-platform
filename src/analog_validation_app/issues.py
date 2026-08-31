"""Stable, beginner-readable explanations for expected product failures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from analog_validation import (
    AdapterConnectionError,
    AdapterDataError,
    AnalogValidationError,
    CapabilityError,
    ConfigurationError,
    ProtocolError,
    ReplayError,
    ValidationError,
)
from analog_validation.exports import ResultExportExistsError

from .errors import (
    CliUsageError,
    ProductAppError,
    ProductCatalogError,
    ProductRequestError,
)

USER_ISSUE_SCHEMA_VERSION = "user-issue.v1"
MAX_USER_ISSUE_TEXT_CHARS = 1024


class UserIssueCode(str, Enum):
    """Stable issue families that presentation layers can handle explicitly."""

    INVALID_REQUEST = "INVALID_REQUEST"
    CATALOG_NOT_FOUND = "CATALOG_NOT_FOUND"
    UNSAFE_CONFIGURATION = "UNSAFE_CONFIGURATION"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    DEVICE_CONNECTION = "DEVICE_CONNECTION"
    INPUT_DATA = "INPUT_DATA"
    OUTPUT_EXISTS = "OUTPUT_EXISTS"
    OPERATION_FAILED = "OPERATION_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class UserIssueSeverity(str, Enum):
    """Presentation severity; it does not change engineering outcomes."""

    WARNING = "WARNING"
    ERROR = "ERROR"


def _issue_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProductRequestError(f"{name} must be a non-empty stripped string")
    if len(value) > MAX_USER_ISSUE_TEXT_CHARS:
        raise ProductRequestError(
            f"{name} exceeds {MAX_USER_ISSUE_TEXT_CHARS} characters"
        )
    if not value.isprintable():
        raise ProductRequestError(f"{name} must contain only printable characters")
    return value


@dataclass(frozen=True, slots=True)
class UserIssue:
    """What happened, why it may happen, and one safe next step."""

    code: UserIssueCode
    severity: UserIssueSeverity
    what_happened: str
    possible_cause: str
    safe_next_step: str
    technical_type: str
    schema_version: str = USER_ISSUE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.code, UserIssueCode):
            raise ProductRequestError("code must be a UserIssueCode")
        if not isinstance(self.severity, UserIssueSeverity):
            raise ProductRequestError("severity must be a UserIssueSeverity")
        _issue_text("what_happened", self.what_happened)
        _issue_text("possible_cause", self.possible_cause)
        _issue_text("safe_next_step", self.safe_next_step)
        _issue_text("technical_type", self.technical_type)
        if self.schema_version != USER_ISSUE_SCHEMA_VERSION:
            raise ProductRequestError(
                f"unsupported user issue schema: {self.schema_version}"
            )


def _expected_text(error: BaseException) -> str:
    raw_message = str(error)
    printable = "".join(
        character if character.isprintable() else " " for character in raw_message
    )
    message = " ".join(printable.split())
    if not message:
        return type(error).__name__
    if len(message) > MAX_USER_ISSUE_TEXT_CHARS:
        return f"{message[: MAX_USER_ISSUE_TEXT_CHARS - 3]}..."
    return message


def issue_from_exception(error: BaseException) -> UserIssue:
    """Map expected failures without parsing their English message text."""

    if not isinstance(error, BaseException):
        raise ProductRequestError("error must be a BaseException")
    technical_type = type(error).__name__
    detail = _expected_text(error)

    if isinstance(error, ProductCatalogError):
        return UserIssue(
            UserIssueCode.CATALOG_NOT_FOUND,
            UserIssueSeverity.ERROR,
            detail,
            "The requested source/profile identity is not in the reviewed catalog.",
            "List the available profiles and select an exact name/version pair.",
            technical_type,
        )
    if isinstance(error, (CliUsageError, ProductRequestError, ValidationError)):
        return UserIssue(
            UserIssueCode.INVALID_REQUEST,
            UserIssueSeverity.ERROR,
            detail,
            "A command, value, type, or required field is missing or invalid.",
            "Run 'analog-validation --help' and correct the requested value.",
            technical_type,
        )
    if isinstance(error, ConfigurationError):
        return UserIssue(
            UserIssueCode.UNSAFE_CONFIGURATION,
            UserIssueSeverity.ERROR,
            detail,
            "The configuration is incomplete, inconsistent, or outside a safe gate.",
            "Review the profile, channels, units, ranges, and output permission.",
            technical_type,
        )
    if isinstance(error, CapabilityError):
        return UserIssue(
            UserIssueCode.CAPABILITY_UNAVAILABLE,
            UserIssueSeverity.WARNING,
            detail,
            "The selected source does not declare the requested operation.",
            "Choose a supported read-only workflow or a reviewed compatible adapter.",
            technical_type,
        )
    if isinstance(error, ResultExportExistsError):
        return UserIssue(
            UserIssueCode.OUTPUT_EXISTS,
            UserIssueSeverity.WARNING,
            detail,
            "The destination already exists and replacement is disabled by default.",
            "Choose a new output path or explicitly review overwrite later.",
            technical_type,
        )
    if isinstance(error, AdapterConnectionError):
        return UserIssue(
            UserIssueCode.DEVICE_CONNECTION,
            UserIssueSeverity.ERROR,
            detail,
            "The selected adapter could not establish or release its resource.",
            "Stop the job, confirm the explicit source, and check that it is available.",
            technical_type,
        )
    if isinstance(error, (ProtocolError, ReplayError, AdapterDataError)):
        return UserIssue(
            UserIssueCode.INPUT_DATA,
            UserIssueSeverity.ERROR,
            detail,
            "Received bytes, replay content, or adapter data failed a strict contract.",
            "Keep the original evidence and verify its declared format/profile.",
            technical_type,
        )
    if isinstance(error, (ProductAppError, AnalogValidationError)):
        return UserIssue(
            UserIssueCode.OPERATION_FAILED,
            UserIssueSeverity.ERROR,
            detail,
            "The product stopped at an expected guarded boundary.",
            "Review the operation details and retry only after correcting the cause.",
            technical_type,
        )
    return UserIssue(
        UserIssueCode.INTERNAL_ERROR,
        UserIssueSeverity.ERROR,
        "The product encountered an unexpected internal error.",
        "This may be a software defect rather than a user or device problem.",
        "Stop the operation and rerun with developer diagnostics before reporting it.",
        technical_type,
    )


def user_issue_to_dict(issue: UserIssue) -> dict[str, str]:
    """Return a deterministic machine view for future CLI and Dashboard use."""

    if not isinstance(issue, UserIssue):
        raise ProductRequestError("issue must be a UserIssue")
    return {
        "schema_version": issue.schema_version,
        "code": issue.code.value,
        "severity": issue.severity.value,
        "what_happened": issue.what_happened,
        "possible_cause": issue.possible_cause,
        "safe_next_step": issue.safe_next_step,
        "technical_type": issue.technical_type,
    }


__all__ = [
    "MAX_USER_ISSUE_TEXT_CHARS",
    "USER_ISSUE_SCHEMA_VERSION",
    "UserIssue",
    "UserIssueCode",
    "UserIssueSeverity",
    "issue_from_exception",
    "user_issue_to_dict",
]
