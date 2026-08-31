from __future__ import annotations

from typing import Any

import pytest

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
from analog_validation.exports import (
    ResultExportExistsError,
    ResultExportFormatError,
    ResultExportLimitError,
    ResultExportPathError,
)
from analog_validation_app import (
    MAX_USER_ISSUE_TEXT_CHARS,
    USER_ISSUE_SCHEMA_VERSION,
    CliUsageError,
    ProductAppError,
    ProductCatalogError,
    ProductDependencyError,
    ProductFeatureUnavailableError,
    ProductReportExistsError,
    ProductReportFormatError,
    ProductReportLimitError,
    ProductReportPathError,
    ProductRequestError,
    ProductServiceError,
    UserIssue,
    UserIssueCode,
    UserIssueSeverity,
    issue_from_exception,
    user_issue_to_dict,
)


def make_issue(**overrides: Any) -> UserIssue:
    values: dict[str, Any] = {
        "code": UserIssueCode.INVALID_REQUEST,
        "severity": UserIssueSeverity.ERROR,
        "what_happened": "A value was invalid.",
        "possible_cause": "The input did not match the contract.",
        "safe_next_step": "Review the documented value.",
        "technical_type": "ExampleError",
    }
    values.update(overrides)
    return UserIssue(**values)


def test_user_issue_is_versioned_and_has_stable_machine_view() -> None:
    issue = make_issue()

    assert USER_ISSUE_SCHEMA_VERSION == "user-issue.v1"
    assert user_issue_to_dict(issue) == {
        "schema_version": "user-issue.v1",
        "code": "INVALID_REQUEST",
        "severity": "ERROR",
        "what_happened": "A value was invalid.",
        "possible_cause": "The input did not match the contract.",
        "safe_next_step": "Review the documented value.",
        "technical_type": "ExampleError",
    }


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"code": "INVALID_REQUEST"}, "UserIssueCode"),
        ({"severity": "ERROR"}, "UserIssueSeverity"),
        ({"what_happened": ""}, "what_happened"),
        ({"possible_cause": " padded "}, "possible_cause"),
        ({"safe_next_step": "line\nbreak"}, "printable"),
        ({"technical_type": "x" * (MAX_USER_ISSUE_TEXT_CHARS + 1)}, "exceeds"),
        ({"schema_version": "user-issue.v2"}, "unsupported"),
    ],
)
def test_user_issue_rejects_invalid_presentation_contracts(
    overrides: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ProductRequestError, match=message):
        make_issue(**overrides)


@pytest.mark.parametrize(
    ("error", "code", "severity"),
    [
        (
            ProductCatalogError("profile missing"),
            UserIssueCode.CATALOG_NOT_FOUND,
            UserIssueSeverity.ERROR,
        ),
        (
            CliUsageError("bad option"),
            UserIssueCode.INVALID_REQUEST,
            UserIssueSeverity.ERROR,
        ),
        (
            ProductRequestError("bad request"),
            UserIssueCode.INVALID_REQUEST,
            UserIssueSeverity.ERROR,
        ),
        (
            ValidationError("bad value"),
            UserIssueCode.INVALID_REQUEST,
            UserIssueSeverity.ERROR,
        ),
        (
            ConfigurationError("unsafe config"),
            UserIssueCode.UNSAFE_CONFIGURATION,
            UserIssueSeverity.ERROR,
        ),
        (
            CapabilityError("read unavailable"),
            UserIssueCode.CAPABILITY_UNAVAILABLE,
            UserIssueSeverity.WARNING,
        ),
        (
            ProductFeatureUnavailableError("reserved command"),
            UserIssueCode.CAPABILITY_UNAVAILABLE,
            UserIssueSeverity.WARNING,
        ),
        (
            ProductDependencyError("serial extra missing"),
            UserIssueCode.OPTIONAL_DEPENDENCY,
            UserIssueSeverity.ERROR,
        ),
        (
            ResultExportExistsError("destination exists"),
            UserIssueCode.OUTPUT_EXISTS,
            UserIssueSeverity.WARNING,
        ),
        (
            ProductReportExistsError("report exists"),
            UserIssueCode.OUTPUT_EXISTS,
            UserIssueSeverity.WARNING,
        ),
        (
            ProductReportPathError("bad output parent"),
            UserIssueCode.OUTPUT_PATH,
            UserIssueSeverity.ERROR,
        ),
        (
            ProductReportFormatError("bad report input"),
            UserIssueCode.INPUT_DATA,
            UserIssueSeverity.ERROR,
        ),
        (
            ProductReportLimitError("too many points"),
            UserIssueCode.INPUT_DATA,
            UserIssueSeverity.ERROR,
        ),
        (
            ResultExportFormatError("bad JSON"),
            UserIssueCode.INPUT_DATA,
            UserIssueSeverity.ERROR,
        ),
        (
            ResultExportLimitError("too large"),
            UserIssueCode.INPUT_DATA,
            UserIssueSeverity.ERROR,
        ),
        (
            ResultExportPathError("missing input"),
            UserIssueCode.INPUT_DATA,
            UserIssueSeverity.ERROR,
        ),
        (
            AdapterConnectionError("port busy"),
            UserIssueCode.DEVICE_CONNECTION,
            UserIssueSeverity.ERROR,
        ),
        (
            ProtocolError("bad CRC"),
            UserIssueCode.INPUT_DATA,
            UserIssueSeverity.ERROR,
        ),
        (
            ReplayError("bad replay"),
            UserIssueCode.INPUT_DATA,
            UserIssueSeverity.ERROR,
        ),
        (
            AdapterDataError("bad adapter data"),
            UserIssueCode.INPUT_DATA,
            UserIssueSeverity.ERROR,
        ),
        (
            ProductAppError("guarded product failure"),
            UserIssueCode.OPERATION_FAILED,
            UserIssueSeverity.ERROR,
        ),
        (
            ProductServiceError("service invariant failed"),
            UserIssueCode.OPERATION_FAILED,
            UserIssueSeverity.ERROR,
        ),
        (
            AnalogValidationError("guarded core failure"),
            UserIssueCode.OPERATION_FAILED,
            UserIssueSeverity.ERROR,
        ),
        (
            RuntimeError("secret internal detail"),
            UserIssueCode.INTERNAL_ERROR,
            UserIssueSeverity.ERROR,
        ),
    ],
)
def test_exception_mapping_uses_types_not_message_parsing(
    error: BaseException,
    code: UserIssueCode,
    severity: UserIssueSeverity,
) -> None:
    issue = issue_from_exception(error)

    assert issue.code is code
    assert issue.severity is severity
    assert issue.technical_type == type(error).__name__
    if code is UserIssueCode.INTERNAL_ERROR:
        assert "secret internal detail" not in issue.what_happened
    else:
        assert str(error) in issue.what_happened


def test_expected_error_text_is_sanitized_bounded_and_never_empty() -> None:
    sanitized = issue_from_exception(CliUsageError("line\nbreak"))
    unnamed = issue_from_exception(CliUsageError())
    long = issue_from_exception(CliUsageError("x" * (MAX_USER_ISSUE_TEXT_CHARS + 100)))

    assert sanitized.what_happened == "line break"
    assert unnamed.what_happened == "CliUsageError"
    assert len(long.what_happened) == MAX_USER_ISSUE_TEXT_CHARS
    assert long.what_happened.endswith("...")


def test_issue_helpers_reject_wrong_runtime_types() -> None:
    with pytest.raises(ProductRequestError, match="BaseException"):
        issue_from_exception("not an exception")  # type: ignore[arg-type]
    with pytest.raises(ProductRequestError, match="UserIssue"):
        user_issue_to_dict(object())  # type: ignore[arg-type]
