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


class ProductServiceError(ProductAppError):
    """A product application service cannot safely complete its operation."""


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
    "ProductDependencyError",
    "ProductFeatureUnavailableError",
    "ProductJobCancelled",
    "ProductRequestError",
    "ProductServiceError",
    "ProductWorkerBusyError",
    "ProductWorkerClosedError",
    "ProductWorkerContractError",
    "ProductWorkerError",
    "ProductWorkerTimeoutError",
]
