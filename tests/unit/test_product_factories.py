from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import analog_validation_app.factories as factories_module
from analog_validation import (
    AdapterState,
    ChannelRange,
    CsvReplayAdapter,
    CsvReplayAdapterConfig,
    DeviceCapabilities,
    EvidenceSource,
    MeasurementUnit,
    ReplayChannelConfig,
    ReplayChannelKind,
    ReplayError,
    SafeRange,
    SimulatorConfig,
)
from analog_validation.profiles import (
    AFE_V1_SERIAL_IDENTITY,
    MSP430_HEALTH_V1_SERIAL_IDENTITY,
)
from analog_validation.replay import load_csv_replay
from analog_validation.serial_adapters import SerialAdapter
from analog_validation.transport import SerialPortInfo
from analog_validation_app import (
    MAX_SERIAL_CHANNEL_ALIASES,
    SERIAL_CHANNEL_ALIAS_SCHEMA_VERSION,
    SERIAL_SOURCE_CONFIG_SCHEMA_VERSION,
    ProductDependencyError,
    ProductJobRequest,
    ProductJobType,
    ProductRequestError,
    ProductSourceMode,
    SerialChannelAlias,
    SerialSourceConfig,
    default_serial_backend_factory,
    discover_serial_ports,
    make_csv_replay_adapter_factory,
    make_csv_replay_dataset_adapter_factory,
    make_serial_adapter_factory,
    make_simulator_adapter_factory,
)
from tests.support import MemorySerialBackend

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_REPLAY = ROOT / "test-data" / "golden" / "csv_replay_v1_valid.csv"


def request(
    source: ProductSourceMode,
    job: ProductJobType = ProductJobType.READ,
    *,
    name: str = "afe",
    version: str = "1",
) -> ProductJobRequest:
    return ProductJobRequest("factory-test", source, job, name, version)


def replay_input_config() -> CsvReplayAdapterConfig:
    return CsvReplayAdapterConfig(
        (
            ReplayChannelConfig(
                "afe.ch0.input",
                ReplayChannelKind.ANALOG,
                MeasurementUnit.MILLIVOLT,
                SafeRange(0, 3300, MeasurementUnit.MILLIVOLT),
            ),
        )
    )


def test_simulator_factory_is_deferred_exact_and_disconnected() -> None:
    config = SimulatorConfig(seed=99)
    factory = make_simulator_adapter_factory(config)

    adapter = factory(request(ProductSourceMode.SIMULATOR))

    assert adapter.state is AdapterState.DISCONNECTED
    assert adapter.simulator_config is config  # type: ignore[attr-defined]


@pytest.mark.parametrize("value", [None, object(), "config"])
def test_simulator_factory_requires_a_config(value: object) -> None:
    with pytest.raises(ProductRequestError, match="SimulatorConfig"):
        make_simulator_adapter_factory(cast(Any, value))


def test_simulator_factory_rejects_source_profile_and_job_mismatches() -> None:
    factory = make_simulator_adapter_factory(SimulatorConfig())
    with pytest.raises(ProductRequestError, match="SIMULATOR"):
        factory(request(ProductSourceMode.CSV_REPLAY))
    mismatched = make_simulator_adapter_factory(SimulatorConfig(profile_version="2"))
    with pytest.raises(ProductRequestError, match="does not match"):
        mismatched(request(ProductSourceMode.SIMULATOR))


def test_replay_factory_loads_lazily_and_projects_explicit_channels() -> None:
    factory = make_csv_replay_adapter_factory(GOLDEN_REPLAY, replay_input_config())

    adapter = cast(CsvReplayAdapter, factory(request(ProductSourceMode.CSV_REPLAY)))

    assert adapter.state is AdapterState.DISCONNECTED
    assert {record.channel for record in adapter.dataset.records} == {"afe.ch0.input"}
    assert len(adapter.dataset.records) == 2
    assert adapter.dataset.dataset_id == "afe-demo-001"


def test_replay_factory_defers_missing_file_until_worker_construction(
    tmp_path: Path,
) -> None:
    factory = make_csv_replay_adapter_factory(
        tmp_path / "missing.csv", replay_input_config()
    )

    with pytest.raises(ReplayError, match="cannot access"):
        factory(request(ProductSourceMode.CSV_REPLAY))


@pytest.mark.parametrize(
    ("path", "config", "message"),
    [
        (object(), replay_input_config(), "path-like"),
        (GOLDEN_REPLAY, object(), "CsvReplayAdapterConfig"),
    ],
)
def test_replay_factory_validates_construction_inputs(
    path: object, config: object, message: str
) -> None:
    with pytest.raises(ProductRequestError, match=message):
        make_csv_replay_adapter_factory(cast(Any, path), cast(Any, config))


def test_prevalidated_replay_factory_requires_exact_dataset_and_config() -> None:
    dataset = load_csv_replay(GOLDEN_REPLAY)
    with pytest.raises(ProductRequestError, match="CsvReplayDataset"):
        make_csv_replay_dataset_adapter_factory(
            cast(Any, object()), replay_input_config()
        )
    with pytest.raises(ProductRequestError, match="CsvReplayAdapterConfig"):
        make_csv_replay_dataset_adapter_factory(dataset, cast(Any, object()))


def test_replay_factory_rejects_source_and_profile_mismatch() -> None:
    factory = make_csv_replay_adapter_factory(GOLDEN_REPLAY, replay_input_config())
    with pytest.raises(ProductRequestError, match="CSV_REPLAY"):
        factory(request(ProductSourceMode.SIMULATOR))
    mismatch = make_csv_replay_adapter_factory(
        GOLDEN_REPLAY,
        CsvReplayAdapterConfig(
            replay_input_config().channels,
            profile_version="2",
        ),
    )
    with pytest.raises(ProductRequestError, match="does not match"):
        mismatch(request(ProductSourceMode.CSV_REPLAY))


def test_adapter_validation_rejects_nonrequest_and_unsupported_profile_source() -> None:
    factory = make_simulator_adapter_factory(SimulatorConfig())
    with pytest.raises(ProductRequestError, match="ProductJobRequest"):
        factory(cast(Any, object()))
    with pytest.raises(ProductRequestError, match="does not support"):
        factory(
            request(
                ProductSourceMode.SIMULATOR,
                name=MSP430_HEALTH_V1_SERIAL_IDENTITY.name,
                version=MSP430_HEALTH_V1_SERIAL_IDENTITY.version,
            )
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"port_id": ""}, "port_id"),
        ({"port_id": " COM1"}, "port_id"),
        ({"port_id": "COM\n1"}, "port_id"),
        ({"baud_rate": True}, "baud_rate"),
        ({"baud_rate": 0}, "baud_rate"),
        ({"read_timeout_seconds": "1"}, "read_timeout_seconds"),
        ({"read_timeout_seconds": float("nan")}, "read_timeout_seconds"),
        ({"max_polls_per_operation": 0}, "max_polls_per_operation"),
        ({"max_buffered_measurements": 10_001}, "max_buffered_measurements"),
        ({"evidence_source": EvidenceSource.THEORY}, "evidence_source"),
    ],
)
def test_serial_source_config_rejects_unbounded_or_misleading_values(
    overrides: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {"port_id": "MEMORY:1"}
    values.update(overrides)
    with pytest.raises(ProductRequestError, match=message):
        SerialSourceConfig(**cast(Any, values))


def test_serial_channel_alias_is_versioned_strict_and_deterministic() -> None:
    alias = SerialChannelAlias.parse(" adc1 = afe.ch0.output ")

    assert alias.native_channel == "adc1"
    assert alias.canonical_channel == "afe.ch0.output"
    assert alias.display == "adc1->afe.ch0.output"
    assert alias.schema_version == SERIAL_CHANNEL_ALIAS_SCHEMA_VERSION
    assert SERIAL_SOURCE_CONFIG_SCHEMA_VERSION == "serial-source-config.v1"


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("adc0", "native=canonical"),
        ("adc0=afe.ch0.input=extra", "native=canonical"),
        ("dac0=afe.ch0.input", "native_channel"),
        ("adc00=afe.ch0.input", "native_channel"),
        ("adc0=afe.ch00.input", "canonical_channel"),
        ("adc256=afe.ch0.input", "outside 0..255"),
        ("adc0=afe.ch256.input", "outside 0..255"),
        ("adc0=afe.ch0.threshold", "canonical_channel"),
    ],
)
def test_serial_channel_alias_rejects_ambiguous_or_out_of_range_text(
    value: str,
    message: str,
) -> None:
    with pytest.raises(ProductRequestError, match=message):
        SerialChannelAlias.parse(value)


def test_serial_channel_alias_and_source_config_reject_contract_drift() -> None:
    with pytest.raises(ProductRequestError, match="unsupported serial channel alias"):
        SerialChannelAlias("adc0", "afe.ch0.input", schema_version="future")
    with pytest.raises(ProductRequestError, match="unsupported serial source config"):
        SerialSourceConfig("MEMORY:1", schema_version="future")


def test_serial_source_config_requires_identity_for_unique_bounded_afe_aliases() -> None:
    input_alias = SerialChannelAlias("adc0", "afe.ch0.input")
    output_alias = SerialChannelAlias("adc1", "afe.ch0.output")

    with pytest.raises(ProductRequestError, match="require expected_device_id"):
        SerialSourceConfig("MEMORY:1", afe_adc_channel_aliases=(input_alias,))
    with pytest.raises(ProductRequestError, match="tuple"):
        SerialSourceConfig(
            "MEMORY:1",
            expected_device_id="device",
            afe_adc_channel_aliases=cast(Any, [input_alias]),
        )
    with pytest.raises(ProductRequestError, match="repeat a native"):
        SerialSourceConfig(
            "MEMORY:1",
            expected_device_id="device",
            afe_adc_channel_aliases=(
                input_alias,
                SerialChannelAlias("adc0", "afe.ch1.input"),
            ),
        )
    with pytest.raises(ProductRequestError, match="repeat a canonical"):
        SerialSourceConfig(
            "MEMORY:1",
            expected_device_id="device",
            afe_adc_channel_aliases=(
                input_alias,
                SerialChannelAlias("adc1", "afe.ch0.input"),
            ),
        )
    with pytest.raises(ProductRequestError, match="exceeds"):
        SerialSourceConfig(
            "MEMORY:1",
            expected_device_id="device",
            afe_adc_channel_aliases=tuple(
                SerialChannelAlias(f"adc{index}", f"afe.ch{index}.input")
                for index in range(MAX_SERIAL_CHANNEL_ALIASES + 1)
            ),
        )
    with pytest.raises(ProductRequestError, match="expected_device_id"):
        SerialSourceConfig("MEMORY:1", expected_device_id=" device")
    with pytest.raises(ProductRequestError, match="exceeds"):
        SerialSourceConfig("MEMORY:1", expected_device_id="d" * 129)

    valid = SerialSourceConfig(
        "MEMORY:1",
        expected_device_id="device",
        afe_adc_channel_aliases=(input_alias, output_alias),
    )
    assert valid.afe_adc_channel_aliases == (input_alias, output_alias)


def test_afe_alias_projection_rejects_cross_category_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    safe_range = SafeRange(0, 3300, MeasurementUnit.MILLIVOLT)
    native = DeviceCapabilities(
        "device",
        "afe",
        "1",
        adc_channels=("adc0",),
        safe_input_ranges=(ChannelRange("adc0", safe_range),),
    )
    malicious_projection = DeviceCapabilities(
        "device",
        "afe",
        "1",
        adc_channels=("afe.ch0.input",),
        digital_input_channels=("afe.ch0.input",),
        safe_input_ranges=(ChannelRange("afe.ch0.input", safe_range),),
    )
    monkeypatch.setattr(
        factories_module,
        "project_afe_v1_read_only_capabilities",
        lambda _native: malicious_projection,
    )

    with pytest.raises(factories_module.ConfigurationError, match="collide"):
        factories_module._project_afe_product_capabilities(
            native,
            (SerialChannelAlias("adc0", "afe.ch0.input"),),
        )


def test_afe_aliases_are_rejected_for_other_profiles_before_backend_creation() -> None:
    created: list[MemorySerialBackend] = []

    def backend_factory() -> MemorySerialBackend:
        backend = MemorySerialBackend()
        created.append(backend)
        return backend

    factory = make_serial_adapter_factory(
        SerialSourceConfig(
            "MEMORY:1",
            expected_device_id="device",
            afe_adc_channel_aliases=(
                SerialChannelAlias("adc0", "afe.ch0.input"),
            ),
        ),
        backend_factory=backend_factory,
    )

    with pytest.raises(ProductRequestError, match="only by the AFE v1 profile"):
        factory(
            request(
                ProductSourceMode.SERIAL_READ_ONLY,
                name=MSP430_HEALTH_V1_SERIAL_IDENTITY.name,
                version=MSP430_HEALTH_V1_SERIAL_IDENTITY.version,
            )
        )
    assert created == []


def test_serial_factory_constructs_exact_receive_only_profiles_without_opening() -> (
    None
):
    created: list[MemorySerialBackend] = []

    def backend_factory() -> MemorySerialBackend:
        backend = MemorySerialBackend()
        created.append(backend)
        return backend

    factory = make_serial_adapter_factory(
        SerialSourceConfig("MEMORY:SERIAL"), backend_factory=backend_factory
    )
    afe = factory(request(ProductSourceMode.SERIAL_READ_ONLY))
    msp = factory(
        request(
            ProductSourceMode.SERIAL_READ_ONLY,
            name=MSP430_HEALTH_V1_SERIAL_IDENTITY.name,
            version=MSP430_HEALTH_V1_SERIAL_IDENTITY.version,
        )
    )

    assert isinstance(afe, SerialAdapter)
    assert isinstance(msp, SerialAdapter)
    assert afe.profile_identity is AFE_V1_SERIAL_IDENTITY
    assert msp.profile_identity is MSP430_HEALTH_V1_SERIAL_IDENTITY
    assert all(backend.open_calls == [] for backend in created)


@pytest.mark.parametrize("value", [None, object(), "config"])
def test_serial_factory_requires_a_serial_config(value: object) -> None:
    with pytest.raises(ProductRequestError, match="SerialSourceConfig"):
        make_serial_adapter_factory(cast(Any, value))


def test_serial_factory_requires_callable_backend_and_read_job() -> None:
    config = SerialSourceConfig("MEMORY:SERIAL")
    with pytest.raises(ProductRequestError, match="backend_factory"):
        make_serial_adapter_factory(config, backend_factory=cast(Any, object()))
    factory = make_serial_adapter_factory(config, backend_factory=MemorySerialBackend)
    with pytest.raises(ProductRequestError, match="does not support"):
        factory(
            request(
                ProductSourceMode.SERIAL_READ_ONLY,
                ProductJobType.DC_ANALYSIS,
            )
        )


def test_default_serial_backend_reports_missing_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(factories_module, "find_spec", lambda _name: None)
    with pytest.raises(ProductDependencyError, match="serial"):
        default_serial_backend_factory()


def test_default_serial_backend_rejects_missing_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(factories_module, "find_spec", lambda _name: object())
    monkeypatch.setattr(
        factories_module,
        "import_module",
        lambda _name: SimpleNamespace(PySerialBackend=None),
    )
    with pytest.raises(ProductDependencyError, match="entry point"):
        default_serial_backend_factory()


def test_default_serial_backend_constructs_lazy_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = MemorySerialBackend()
    monkeypatch.setattr(factories_module, "find_spec", lambda _name: object())
    monkeypatch.setattr(
        factories_module,
        "import_module",
        lambda _name: SimpleNamespace(PySerialBackend=lambda: expected),
    )
    assert default_serial_backend_factory() is expected


def test_port_discovery_closes_backend_without_opening() -> None:
    backend = MemorySerialBackend(ports=(SerialPortInfo("MEMORY:1", "Test port"),))

    ports = discover_serial_ports(lambda: backend)

    assert ports == (SerialPortInfo("MEMORY:1", "Test port"),)
    assert backend.discover_calls == 1
    assert backend.open_calls == []
    assert backend.close_calls == 1


def test_port_discovery_validates_factory_and_backend_result() -> None:
    with pytest.raises(ProductRequestError, match="backend_factory"):
        discover_serial_ports(cast(Any, object()))
    backend = MemorySerialBackend.scripted(discover=([],))
    with pytest.raises(ProductRequestError, match="SerialPortInfo"):
        discover_serial_ports(lambda: backend)
    assert backend.close_calls == 1


def test_port_discovery_rejects_duplicate_logical_ids_and_closes_backend() -> None:
    backend = MemorySerialBackend(
        ports=(
            SerialPortInfo("MEMORY:1", "First"),
            SerialPortInfo("MEMORY:1", "Duplicate"),
        )
    )

    with pytest.raises(ProductRequestError, match="duplicate port IDs"):
        discover_serial_ports(lambda: backend)

    assert backend.open_calls == []
    assert backend.close_calls == 1
