"""Product-shell contracts for Analog Validation Studio.

Importing this package does not import pyserial, Tk, or open any resources.
"""

from analog_validation import __version__

from .catalog import (
    MAX_CATALOG_TEXT_CHARS,
    PRODUCT_CATALOG_SCHEMA_VERSION,
    PRODUCT_PROFILES,
    PRODUCT_SOURCES,
    ProductProfileDescriptor,
    ProductSourceDescriptor,
    get_product_profile,
    get_product_source,
    list_product_profiles,
    list_product_sources,
)
from .errors import (
    CliUsageError,
    ProductAppError,
    ProductCatalogError,
    ProductCliError,
    ProductRequestError,
)
from .issues import (
    MAX_USER_ISSUE_TEXT_CHARS,
    USER_ISSUE_SCHEMA_VERSION,
    UserIssue,
    UserIssueCode,
    UserIssueSeverity,
    issue_from_exception,
    user_issue_to_dict,
)
from .models import (
    MAX_PRODUCT_IDENTIFIER_CHARS,
    MAX_PRODUCT_LIMITATION_CHARS,
    MAX_PRODUCT_LIMITATIONS,
    PRODUCT_JOB_SCHEMA_VERSION,
    PRODUCT_RESULT_SCHEMA_VERSION,
    ProductJobRequest,
    ProductJobResult,
    ProductJobType,
    ProductResultStatus,
    ProductSourceMode,
)

__all__ = [
    "MAX_CATALOG_TEXT_CHARS",
    "MAX_PRODUCT_IDENTIFIER_CHARS",
    "MAX_PRODUCT_LIMITATIONS",
    "MAX_PRODUCT_LIMITATION_CHARS",
    "MAX_USER_ISSUE_TEXT_CHARS",
    "PRODUCT_CATALOG_SCHEMA_VERSION",
    "PRODUCT_JOB_SCHEMA_VERSION",
    "PRODUCT_PROFILES",
    "PRODUCT_RESULT_SCHEMA_VERSION",
    "PRODUCT_SOURCES",
    "USER_ISSUE_SCHEMA_VERSION",
    "CliUsageError",
    "ProductAppError",
    "ProductCatalogError",
    "ProductCliError",
    "ProductJobRequest",
    "ProductJobResult",
    "ProductJobType",
    "ProductProfileDescriptor",
    "ProductRequestError",
    "ProductResultStatus",
    "ProductSourceDescriptor",
    "ProductSourceMode",
    "UserIssue",
    "UserIssueCode",
    "UserIssueSeverity",
    "__version__",
    "get_product_profile",
    "get_product_source",
    "issue_from_exception",
    "list_product_profiles",
    "list_product_sources",
    "user_issue_to_dict",
]
