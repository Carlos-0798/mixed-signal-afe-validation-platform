from __future__ import annotations

from typing import Any

import pytest

import analog_validation_app.catalog as catalog_module
from analog_validation import EvidenceSource
from analog_validation_app import (
    MAX_CATALOG_TEXT_CHARS,
    PRODUCT_CATALOG_SCHEMA_VERSION,
    PRODUCT_PROFILES,
    PRODUCT_SOURCES,
    ProductCatalogError,
    ProductJobType,
    ProductProfileDescriptor,
    ProductSourceDescriptor,
    ProductSourceMode,
    get_product_profile,
    get_product_source,
    list_product_profiles,
    list_product_sources,
)


def source_values(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "mode": ProductSourceMode.SIMULATOR,
        "display_name": "Simulator",
        "summary": "Deterministic software source.",
        "evidence_sources": (EvidenceSource.SYNTHETIC,),
        "supported_jobs": (ProductJobType.READ,),
    }
    values.update(overrides)
    return values


def profile_values(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "name": "example",
        "version": "1",
        "display_name": "Example v1",
        "summary": "Read-only example profile.",
        "source_modes": (ProductSourceMode.SIMULATOR,),
    }
    values.update(overrides)
    return values


def test_catalog_has_deterministic_sources_and_independent_profiles() -> None:
    assert list_product_sources() is PRODUCT_SOURCES
    assert list_product_profiles() is PRODUCT_PROFILES
    assert [source.mode for source in PRODUCT_SOURCES] == [
        ProductSourceMode.SIMULATOR,
        ProductSourceMode.CSV_REPLAY,
        ProductSourceMode.SERIAL_READ_ONLY,
    ]
    assert sum(source.is_default for source in PRODUCT_SOURCES) == 1
    assert PRODUCT_SOURCES[0].evidence_sources == (EvidenceSource.SYNTHETIC,)
    assert PRODUCT_SOURCES[2].requires_serial_extra is True
    assert PRODUCT_SOURCES[2].supported_jobs == (
        ProductJobType.READ,
        ProductJobType.LIVE_MONITOR,
    )

    assert [profile.identity for profile in PRODUCT_PROFILES] == [
        "afe/1",
        "msp430-equipment-health/1",
    ]
    assert all(profile.product_read_only for profile in PRODUCT_PROFILES)
    assert PRODUCT_PROFILES[1].source_modes == (
        ProductSourceMode.SERIAL_READ_ONLY,
    )
    assert PRODUCT_CATALOG_SCHEMA_VERSION == "product-catalog.v1"


@pytest.mark.parametrize("mode", list(ProductSourceMode))
def test_exact_source_lookup_requires_an_enum(mode: ProductSourceMode) -> None:
    assert get_product_source(mode).mode is mode


def test_source_lookup_rejects_strings_and_unlisted_enum_members(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ProductCatalogError, match="ProductSourceMode"):
        get_product_source("SIMULATOR")  # type: ignore[arg-type]

    monkeypatch.setattr(catalog_module, "PRODUCT_SOURCES", PRODUCT_SOURCES[:1])
    with pytest.raises(ProductCatalogError, match="unknown product source"):
        get_product_source(ProductSourceMode.CSV_REPLAY)


def test_exact_profile_lookup_never_infers_a_version() -> None:
    assert get_product_profile("afe", "1") is PRODUCT_PROFILES[0]
    assert get_product_profile("msp430-equipment-health", "1") is PRODUCT_PROFILES[1]
    with pytest.raises(ProductCatalogError, match="unknown product profile"):
        get_product_profile("afe", "2")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"mode": "SIMULATOR"}, "ProductSourceMode"),
        ({"display_name": ""}, "display_name"),
        ({"display_name": " padded "}, "display_name"),
        ({"summary": "line\nbreak"}, "printable"),
        ({"summary": "x" * (MAX_CATALOG_TEXT_CHARS + 1)}, "exceeds"),
        ({"evidence_sources": "SYNTHETIC"}, "iterable"),
        ({"evidence_sources": ()}, "cannot be empty"),
        ({"evidence_sources": ("SYNTHETIC",)}, "EvidenceSource"),
        (
            {"evidence_sources": (EvidenceSource.SYNTHETIC,) * 2},
            "duplicates",
        ),
        ({"supported_jobs": 1}, "iterable"),
        ({"supported_jobs": ()}, "cannot be empty"),
        ({"supported_jobs": ("READ",)}, "ProductJobType"),
        ({"supported_jobs": (ProductJobType.READ,) * 2}, "duplicates"),
        ({"requires_serial_extra": 1}, "boolean"),
        ({"is_default": 1}, "boolean"),
        ({"schema_version": "product-catalog.v2"}, "unsupported"),
    ],
)
def test_source_descriptor_rejects_unbounded_or_untyped_values(
    overrides: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ProductCatalogError, match=message):
        ProductSourceDescriptor(**source_values(**overrides))


def test_source_descriptor_freezes_iterables() -> None:
    evidence = [EvidenceSource.SYNTHETIC]
    jobs = [ProductJobType.READ]
    source = ProductSourceDescriptor(
        **source_values(evidence_sources=evidence, supported_jobs=jobs)
    )
    evidence.append(EvidenceSource.HOST_TEST)
    jobs.append(ProductJobType.DC_ANALYSIS)

    assert source.evidence_sources == (EvidenceSource.SYNTHETIC,)
    assert source.supported_jobs == (ProductJobType.READ,)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"name": ""}, "name"),
        ({"version": " 1"}, "version"),
        ({"display_name": "line\nbreak"}, "printable"),
        ({"summary": "x" * (MAX_CATALOG_TEXT_CHARS + 1)}, "exceeds"),
        ({"source_modes": "SIMULATOR"}, "iterable"),
        ({"source_modes": ()}, "cannot be empty"),
        ({"source_modes": ("SIMULATOR",)}, "ProductSourceMode"),
        ({"source_modes": (ProductSourceMode.SIMULATOR,) * 2}, "duplicates"),
        ({"product_read_only": 1}, "boolean"),
        ({"product_read_only": False}, "must be read-only"),
        ({"schema_version": "product-catalog.v2"}, "unsupported"),
    ],
)
def test_profile_descriptor_rejects_ambiguous_or_writable_entries(
    overrides: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ProductCatalogError, match=message):
        ProductProfileDescriptor(**profile_values(**overrides))


def test_profile_descriptor_freezes_sources() -> None:
    sources = [ProductSourceMode.SIMULATOR]
    profile = ProductProfileDescriptor(**profile_values(source_modes=sources))
    sources.append(ProductSourceMode.CSV_REPLAY)

    assert profile.source_modes == (ProductSourceMode.SIMULATOR,)


@pytest.mark.parametrize(
    ("name", "version", "message"),
    [
        ("", "1", "name"),
        (" afe", "1", "name"),
        ("afe", "", "version"),
        ("afe", "line\nbreak", "printable"),
    ],
)
def test_profile_lookup_validates_identity_text(
    name: str,
    version: str,
    message: str,
) -> None:
    with pytest.raises(ProductCatalogError, match=message):
        get_product_profile(name, version)
