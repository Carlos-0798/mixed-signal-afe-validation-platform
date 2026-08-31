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


__all__ = [
    "CliUsageError",
    "ProductAppError",
    "ProductCatalogError",
    "ProductCliError",
    "ProductRequestError",
]
