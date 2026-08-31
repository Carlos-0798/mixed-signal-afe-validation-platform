from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import pytest

from analog_validation import MeasurementUnit, ReadOperation
from analog_validation.exports import result_export_to_dict
from analog_validation_app import (
    MAX_PRODUCT_WORKFLOW_SAMPLES,
    MAX_PRODUCT_WORKFLOW_TEXT_CHARS,
    PRODUCT_WORKFLOW_CONFIG_SCHEMA_VERSION,
    PreparedProductJob,
    ProductJobType,
    ProductRequestError,
    ProductSourceMode,
    ProductWorkerState,
    ProductWorkflowConfiguration,
    SerialSourceConfig,
    execute_product_job,
    prepare_product_job,
)
from tests.support import MemorySerialBackend

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_REPLAY = ROOT / "test-data" / "golden" / "csv_replay_v1_valid.csv"


def simulator_config(
    job: ProductJobType = ProductJobType.READ,
    **changes: object,
) -> ProductWorkflowConfiguration:
    values: dict[str, object] = {
        "source_mode": ProductSourceMode.SIMULATOR,
        "job_type": job,
    }
    values.update(changes)
    return ProductWorkflowConfiguration(**cast(Any, values))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"source_mode": "SIMULATOR"}, "source_mode"),
        ({"job_type": "READ"}, "job_type"),
        ({"profile_name": ""}, "profile_name"),
        ({"profile_name": "x" * (MAX_PRODUCT_WORKFLOW_TEXT_CHARS + 1)}, "exceeds"),
        ({"profile_name": "bad\nname"}, "printable"),
        ({"operation": "ANALOG"}, "operation"),
        ({"unit": "mV"}, "unit"),
        ({"sample_count": True}, "integer"),
        ({"sample_count": MAX_PRODUCT_WORKFLOW_SAMPLES + 1}, "between"),
        ({"rising_count": 1}, "between"),
        ({"rising_count": 6_000, "falling_count": 6_000}, "exceeds"),
        ({"replay_minimum": "0"}, "numeric"),
        ({"replay_minimum": float("nan")}, "finite"),
        ({"replay_minimum": 2, "replay_maximum": 1}, "below"),
        ({"confirm_read_only": "yes"}, "boolean"),
        ({"target_gain": object()}, "numeric"),
        ({"target_gain": float("inf")}, "finite"),
        (
            {
                "source_mode": ProductSourceMode.SIMULATOR,
                "profile_name": "msp430-equipment-health",
            },
            "does not support",
        ),
        (
            {
                "source_mode": ProductSourceMode.SERIAL_READ_ONLY,
                "job_type": ProductJobType.DC_ANALYSIS,
                "serial_config": SerialSourceConfig("MEMORY:1"),
                "confirm_read_only": True,
            },
            "does not support",
        ),
        ({"replay_path": GOLDEN_REPLAY}, "Simulator configuration"),
        ({"confirm_read_only": True}, "does not use"),
        ({"schema_version": "product-workflow-config.v2"}, "unsupported"),
    ],
)
def test_configuration_rejects_invalid_common_and_catalog_values(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ProductRequestError, match=message):
        simulator_config(**cast(Any, changes))


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (
            lambda: ProductWorkflowConfiguration(
                ProductSourceMode.CSV_REPLAY, ProductJobType.READ
            ),
            "replay_path",
        ),
        (
            lambda: ProductWorkflowConfiguration(
                ProductSourceMode.CSV_REPLAY,
                ProductJobType.READ,
                replay_path=GOLDEN_REPLAY,
                serial_config=SerialSourceConfig("MEMORY:1"),
            ),
            "serial settings",
        ),
        (
            lambda: ProductWorkflowConfiguration(
                ProductSourceMode.SERIAL_READ_ONLY,
                ProductJobType.READ,
                replay_path=GOLDEN_REPLAY,
                serial_config=SerialSourceConfig("MEMORY:1"),
                confirm_read_only=True,
            ),
            "replay_path",
        ),
        (
            lambda: ProductWorkflowConfiguration(
                ProductSourceMode.SERIAL_READ_ONLY,
                ProductJobType.READ,
                confirm_read_only=True,
            ),
            "SerialSourceConfig",
        ),
        (
            lambda: ProductWorkflowConfiguration(
                ProductSourceMode.SERIAL_READ_ONLY,
                ProductJobType.READ,
                serial_config=SerialSourceConfig("MEMORY:1"),
            ),
            "confirmation",
        ),
    ],
)
def test_configuration_rejects_inconsistent_source_resources(
    config: Any, message: str
) -> None:
    with pytest.raises(ProductRequestError, match=message):
        config()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {"operation": ReadOperation.DIGITAL},
            "digital reads require boolean",
        ),
        ({"unit": MeasurementUnit.BOOLEAN}, "analog reads cannot"),
        (
            {
                "job_type": ProductJobType.DC_ANALYSIS,
                "unit": MeasurementUnit.BOOLEAN,
            },
            "require V or mV",
        ),
        (
            {
                "job_type": ProductJobType.DC_ANALYSIS,
                "secondary_channel": "afe.ch0.input",
            },
            "must differ",
        ),
        (
            {
                "job_type": ProductJobType.HYSTERESIS_ANALYSIS,
                "state_channel": "afe.ch0.input",
            },
            "must differ",
        ),
    ],
)
def test_configuration_rejects_inconsistent_job_fields(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ProductRequestError, match=message):
        simulator_config(**cast(Any, changes))


def test_digital_read_configuration_is_valid() -> None:
    config = simulator_config(
        operation=ReadOperation.DIGITAL,
        unit=MeasurementUnit.BOOLEAN,
        primary_channel="afe.ch0.threshold",
    )
    assert config.operation is ReadOperation.DIGITAL


def test_prepared_job_contract_and_prepare_arguments_are_strict() -> None:
    prepared = prepare_product_job(simulator_config(), "reviewed-job")
    assert prepared.request.job_id == "reviewed-job"
    assert prepared.review_lines[-1] == "Hardware performance validation: NOT CLAIMED."

    invalid_values = (
        (
            object(),
            prepared.service_factory,
            prepared.output_slot,
            prepared.review_lines,
        ),
        (prepared.request, object(), prepared.output_slot, prepared.review_lines),
        (prepared.request, prepared.service_factory, object(), prepared.review_lines),
        (prepared.request, prepared.service_factory, prepared.output_slot, ()),
    )
    for values in invalid_values:
        with pytest.raises(ProductRequestError):
            PreparedProductJob(*cast(Any, values))
    with pytest.raises(ProductRequestError, match="config"):
        prepare_product_job(cast(Any, object()), "job")
    with pytest.raises(ProductRequestError, match="job_id"):
        prepare_product_job(simulator_config(), " bad")
    with pytest.raises(ProductRequestError, match="backend_factory"):
        prepare_product_job(
            simulator_config(), "job", backend_factory=cast(Any, object())
        )
    with pytest.raises(ProductRequestError, match="prevalidate_replay"):
        prepare_product_job(
            simulator_config(), "job", prevalidate_replay=cast(Any, "yes")
        )
    with pytest.raises(ProductRequestError, match="service_clock"):
        prepare_product_job(
            simulator_config(), "job", service_clock=cast(Any, object())
        )


@pytest.mark.parametrize(
    "job_type",
    [
        ProductJobType.READ,
        ProductJobType.DC_ANALYSIS,
        ProductJobType.HYSTERESIS_ANALYSIS,
    ],
)
def test_simulator_prepared_jobs_execute_through_one_shared_path(
    job_type: ProductJobType,
) -> None:
    config = simulator_config(job_type, sample_count=24)
    prepared = prepare_product_job(config, f"sim-{job_type.value}")

    execution = execute_product_job(
        prepared.request, prepared.service_factory, prepared.output_slot
    )

    assert execution.worker_state is ProductWorkerState.SUCCEEDED
    assert execution.result is not None
    assert execution.output is not None
    assert execution.output.result_export is not None or job_type is ProductJobType.READ


@pytest.mark.parametrize(
    "job_type",
    [ProductJobType.DC_ANALYSIS, ProductJobType.HYSTERESIS_ANALYSIS],
)
def test_analysis_workflows_accept_an_explicit_reproducibility_clock(
    job_type: ProductJobType,
) -> None:
    fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
    prepared = prepare_product_job(
        simulator_config(job_type, sample_count=24),
        f"fixed-{job_type.value}",
        service_clock=lambda: fixed,
    )

    execution = execute_product_job(
        prepared.request, prepared.service_factory, prepared.output_slot
    )

    assert execution.output is not None
    assert execution.output.result_export is not None
    document = result_export_to_dict(execution.output.result_export)
    metadata = cast(
        dict[str, object], cast(dict[str, object], document["test_run"])["metadata"]
    )
    assert metadata["started_at"] == "2026-01-01T00:00:00.000000Z"
    assert metadata["ended_at"] == "2026-01-01T00:00:00.000000Z"


@pytest.mark.parametrize(
    ("job_type", "extra"),
    [
        (ProductJobType.READ, {}),
        (ProductJobType.DC_ANALYSIS, {}),
        (ProductJobType.HYSTERESIS_ANALYSIS, {}),
        (
            ProductJobType.READ,
            {
                "operation": ReadOperation.DIGITAL,
                "unit": MeasurementUnit.BOOLEAN,
                "primary_channel": "afe.ch0.threshold",
            },
        ),
    ],
)
def test_replay_is_prevalidated_and_all_channel_shapes_are_compiled(
    job_type: ProductJobType, extra: dict[str, object]
) -> None:
    config = ProductWorkflowConfiguration(
        ProductSourceMode.CSV_REPLAY,
        job_type,
        replay_path=GOLDEN_REPLAY,
        sample_count=2,
        rising_count=2,
        falling_count=2,
        **cast(Any, extra),
    )

    prepared = prepare_product_job(config, f"replay-{job_type.value}")

    assert any("validated before Run" in line for line in prepared.review_lines)


def test_replay_can_preserve_cli_worker_side_validation_boundary(
    tmp_path: Path,
) -> None:
    config = ProductWorkflowConfiguration(
        ProductSourceMode.CSV_REPLAY,
        ProductJobType.READ,
        replay_path=tmp_path / "missing.csv",
    )
    prepared = prepare_product_job(config, "lazy-replay", prevalidate_replay=False)
    assert any("bounded worker" in line for line in prepared.review_lines)


def test_serial_preparation_is_deferred_and_receive_only() -> None:
    backend = MemorySerialBackend()
    config = ProductWorkflowConfiguration(
        ProductSourceMode.SERIAL_READ_ONLY,
        ProductJobType.READ,
        serial_config=SerialSourceConfig("MEMORY:SERIAL"),
        confirm_read_only=True,
    )

    prepared = prepare_product_job(
        config, "serial-job", backend_factory=lambda: backend
    )

    assert backend.open_calls == []
    assert any("opens only after Run" in line for line in prepared.review_lines)
    assert any("no write command" in line for line in prepared.review_lines)
    assert PRODUCT_WORKFLOW_CONFIG_SCHEMA_VERSION == "product-workflow-config.v1"
