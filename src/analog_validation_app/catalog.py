"""Reviewed product sources and profiles without device auto-detection."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from analog_validation import EvidenceSource
from analog_validation.protocol import AFE_PROFILE_NAME, AFE_PROFILE_VERSION
from analog_validation.protocol.msp430_health_v1 import (
    MSP430_HEALTH_PROFILE_NAME,
    MSP430_HEALTH_PROFILE_VERSION,
)

from .errors import ProductCatalogError
from .models import ProductJobType, ProductSourceMode

PRODUCT_CATALOG_SCHEMA_VERSION = "product-catalog.v1"
MAX_CATALOG_TEXT_CHARS = 512


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProductCatalogError(f"{name} must be a non-empty stripped string")
    if len(value) > MAX_CATALOG_TEXT_CHARS:
        raise ProductCatalogError(
            f"{name} exceeds {MAX_CATALOG_TEXT_CHARS} characters"
        )
    if not value.isprintable():
        raise ProductCatalogError(f"{name} must contain only printable characters")
    return value


def _typed_tuple(
    name: str,
    values: object,
    expected_type: type[object],
) -> tuple[object, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ProductCatalogError(f"{name} must be an iterable")
    frozen = tuple(values)
    if not frozen:
        raise ProductCatalogError(f"{name} cannot be empty")
    if not all(isinstance(value, expected_type) for value in frozen):
        raise ProductCatalogError(
            f"{name} must contain {expected_type.__name__} values"
        )
    if len(frozen) != len(set(frozen)):
        raise ProductCatalogError(f"{name} cannot contain duplicates")
    return frozen


@dataclass(frozen=True, slots=True)
class ProductSourceDescriptor:
    """One explicit source choice and its product-level evidence boundary."""

    mode: ProductSourceMode
    display_name: str
    summary: str
    evidence_sources: tuple[EvidenceSource, ...]
    supported_jobs: tuple[ProductJobType, ...]
    requires_serial_extra: bool = False
    is_default: bool = False
    schema_version: str = PRODUCT_CATALOG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.mode, ProductSourceMode):
            raise ProductCatalogError("mode must be a ProductSourceMode")
        _text("display_name", self.display_name)
        _text("summary", self.summary)
        evidence = _typed_tuple(
            "evidence_sources", self.evidence_sources, EvidenceSource
        )
        jobs = _typed_tuple("supported_jobs", self.supported_jobs, ProductJobType)
        object.__setattr__(self, "evidence_sources", evidence)
        object.__setattr__(self, "supported_jobs", jobs)
        if not isinstance(self.requires_serial_extra, bool):
            raise ProductCatalogError("requires_serial_extra must be boolean")
        if not isinstance(self.is_default, bool):
            raise ProductCatalogError("is_default must be boolean")
        if self.schema_version != PRODUCT_CATALOG_SCHEMA_VERSION:
            raise ProductCatalogError(
                f"unsupported product catalog schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class ProductProfileDescriptor:
    """One public protocol profile and its Phase 5 product access policy."""

    name: str
    version: str
    display_name: str
    summary: str
    source_modes: tuple[ProductSourceMode, ...]
    product_read_only: bool = True
    schema_version: str = PRODUCT_CATALOG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _text("name", self.name)
        _text("version", self.version)
        _text("display_name", self.display_name)
        _text("summary", self.summary)
        modes = _typed_tuple("source_modes", self.source_modes, ProductSourceMode)
        object.__setattr__(self, "source_modes", modes)
        if not isinstance(self.product_read_only, bool):
            raise ProductCatalogError("product_read_only must be boolean")
        if not self.product_read_only:
            raise ProductCatalogError("Phase 5 catalog profiles must be read-only")
        if self.schema_version != PRODUCT_CATALOG_SCHEMA_VERSION:
            raise ProductCatalogError(
                f"unsupported product catalog schema: {self.schema_version}"
            )

    @property
    def identity(self) -> str:
        """Return the explicit name/version pair shown to users."""

        return f"{self.name}/{self.version}"


PRODUCT_SOURCES = (
    ProductSourceDescriptor(
        ProductSourceMode.SIMULATOR,
        "Simulator",
        "Deterministic software records; never physical measurements.",
        (EvidenceSource.SYNTHETIC,),
        (
            ProductJobType.READ,
            ProductJobType.DC_ANALYSIS,
            ProductJobType.HYSTERESIS_ANALYSIS,
        ),
        is_default=True,
    ),
    ProductSourceDescriptor(
        ProductSourceMode.CSV_REPLAY,
        "CSV Replay",
        "Strict local replay that preserves lineage and labels current use as replay.",
        (EvidenceSource.CSV_REPLAY,),
        (
            ProductJobType.READ,
            ProductJobType.DC_ANALYSIS,
            ProductJobType.HYSTERESIS_ANALYSIS,
        ),
    ),
    ProductSourceDescriptor(
        ProductSourceMode.SERIAL_READ_ONLY,
        "Serial (read-only)",
        "Explicit bounded receive-only integration; no command or write surface.",
        (EvidenceSource.HOST_TEST, EvidenceSource.BENCH_CONTROLLER),
        (ProductJobType.READ,),
        requires_serial_extra=True,
    ),
)

PRODUCT_PROFILES = (
    ProductProfileDescriptor(
        AFE_PROFILE_NAME,
        AFE_PROFILE_VERSION,
        "Configurable AFE v1",
        "Controller-neutral AFE records; Phase 5 product access remains receive-only.",
        (
            ProductSourceMode.SIMULATOR,
            ProductSourceMode.CSV_REPLAY,
            ProductSourceMode.SERIAL_READ_ONLY,
        ),
    ),
    ProductProfileDescriptor(
        MSP430_HEALTH_PROFILE_NAME,
        MSP430_HEALTH_PROFILE_VERSION,
        "MSP430 Equipment Health v1",
        "Independent peer telemetry profile with unavailable-safe mapping.",
        (ProductSourceMode.SERIAL_READ_ONLY,),
    ),
)


def list_product_sources() -> tuple[ProductSourceDescriptor, ...]:
    """Return the stable reviewed source catalog in display order."""

    return PRODUCT_SOURCES


def get_product_source(mode: ProductSourceMode) -> ProductSourceDescriptor:
    """Look up one source without guessing from a string or device identity."""

    if not isinstance(mode, ProductSourceMode):
        raise ProductCatalogError("mode must be a ProductSourceMode")
    for source in PRODUCT_SOURCES:
        if source.mode is mode:
            return source
    raise ProductCatalogError(f"unknown product source: {mode.value}")


def list_product_profiles() -> tuple[ProductProfileDescriptor, ...]:
    """Return the stable reviewed profile catalog in display order."""

    return PRODUCT_PROFILES


def get_product_profile(name: str, version: str) -> ProductProfileDescriptor:
    """Look up one exact profile identity; never infer a compatible version."""

    checked_name = _text("name", name)
    checked_version = _text("version", version)
    for profile in PRODUCT_PROFILES:
        if profile.name == checked_name and profile.version == checked_version:
            return profile
    raise ProductCatalogError(
        f"unknown product profile: {checked_name}/{checked_version}"
    )


__all__ = [
    "MAX_CATALOG_TEXT_CHARS",
    "PRODUCT_CATALOG_SCHEMA_VERSION",
    "PRODUCT_PROFILES",
    "PRODUCT_SOURCES",
    "ProductProfileDescriptor",
    "ProductSourceDescriptor",
    "get_product_profile",
    "get_product_source",
    "list_product_profiles",
    "list_product_sources",
]
