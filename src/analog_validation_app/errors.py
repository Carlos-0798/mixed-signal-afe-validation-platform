"""Expected failures owned by the Analog Validation Studio product layer."""


class ProductAppError(Exception):
    """Base class for expected product-shell failures."""


class ProductRequestError(ProductAppError):
    """A product request or presentation contract is invalid."""


class ProductCatalogError(ProductAppError):
    """A requested source or profile is absent from the reviewed catalog."""


class ProductCliError(ProductAppError):
    """A command-line request cannot be accepted."""


class CliUsageError(ProductCliError):
    """Command syntax or options are invalid."""


class ProductFeatureUnavailableError(ProductCliError):
    """A recognized product feature belongs to a later reviewed checkpoint."""


class ProductDependencyError(ProductAppError):
    """An explicitly requested optional runtime dependency is unavailable."""


class ProductDashboardUnavailableError(ProductDependencyError):
    """The explicitly requested local Tk Dashboard cannot be created."""


class ProductServiceError(ProductAppError):
    """A product application service cannot safely complete its operation."""


class ProductDemoError(ProductAppError):
    """Base class for expected deterministic-demo failures."""


class ProductDemoFormatError(ProductDemoError):
    """The demo workflow did not produce its reviewed deterministic contract."""


class ProductDemoPathError(ProductDemoError):
    """A demo destination cannot be prepared or published safely."""


class ProductDemoExistsError(ProductDemoPathError):
    """A demo destination exists while replacement is disabled."""


class ProductReportError(ProductAppError):
    """Base class for expected human-report failures."""


class ProductReportFormatError(ProductReportError):
    """A finalized result cannot be represented by the report contract."""


class ProductReportLimitError(ProductReportError):
    """A report input or output exceeds a bounded product limit."""


class ProductReportPathError(ProductReportError):
    """A report destination cannot be prepared or published safely."""


class ProductReportExistsError(ProductReportPathError):
    """A report destination exists while replacement is disabled."""


class ProductWorkerError(ProductAppError):
    """Base class for expected product-worker failures."""


class ProductWorkerBusyError(ProductWorkerError):
    """A second job was requested while one worker already owns a job."""


class ProductWorkerClosedError(ProductWorkerError):
    """A closed worker cannot accept more jobs."""


class ProductWorkerContractError(ProductWorkerError):
    """An injected job service violated the product-worker contract."""


class ProductWorkerTimeoutError(ProductWorkerError):
    """A bounded join expired before the worker released its job."""


class ProductJobCancelled(ProductWorkerError):
    """Cooperative cancellation was observed at a bounded job checkpoint."""


__all__ = [
    "CliUsageError",
    "ProductAppError",
    "ProductCatalogError",
    "ProductCliError",
    "ProductDashboardUnavailableError",
    "ProductDemoError",
    "ProductDemoExistsError",
    "ProductDemoFormatError",
    "ProductDemoPathError",
    "ProductDependencyError",
    "ProductFeatureUnavailableError",
    "ProductJobCancelled",
    "ProductReportError",
    "ProductReportExistsError",
    "ProductReportFormatError",
    "ProductReportLimitError",
    "ProductReportPathError",
    "ProductRequestError",
    "ProductServiceError",
    "ProductWorkerBusyError",
    "ProductWorkerClosedError",
    "ProductWorkerContractError",
    "ProductWorkerError",
    "ProductWorkerTimeoutError",
]
