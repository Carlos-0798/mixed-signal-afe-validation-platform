from __future__ import annotations

import io
import json
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import Any, cast

import pytest

import analog_validation_app.services as services_module
from analog_validation import (
    ChannelReadRequest,
    DeviceCommand,
    EvidenceSource,
    MeasurementUnit,
    ReadOperation,
    ReadWorkflowRequest,
    SimulatorAdapter,
    SimulatorConfig,
)
from analog_validation.protocol import (
    AFE_PROFILE_NAME,
    AFE_PROFILE_VERSION,
    AfeCapabilityChannel,
    AfeCapabilityDevice,
    AfeCapabilityEnd,
    AfeTelemetry,
    CapabilityChannelKind,
    encode_afe_message,
)
from analog_validation.transport import (
    SerialBackendDisconnected,
    SerialBackendTimeout,
)
from analog_validation_app import (
    LIVE_MONITOR_SCHEMA_VERSION,
    MAX_LIVE_MONITOR_DURATION_SECONDS,
    MAX_LIVE_MONITOR_MAX_POINTS,
    LiveMonitorJobService,
    LiveMonitorSession,
    LiveMonitorSnapshot,
    ProductCancellationToken,
    ProductJobRequest,
    ProductJobType,
    ProductJobWorker,
    ProductRequestError,
    ProductResultStatus,
    ProductServiceError,
    ProductServiceOutput,
    ProductServiceOutputSlot,
    ProductSourceMode,
    ProductWorkerState,
    ProductWorkflowConfiguration,
    SerialChannelAlias,
    SerialSourceConfig,
    execute_product_job,
    get_product_source,
    prepare_product_job,
)
from analog_validation_app.cli import CliDependencies, main
from tests.support import MemorySerialBackend


def _simulator_config(**changes: object) -> ProductWorkflowConfiguration:
    values: dict[str, object] = {
        "source_mode": ProductSourceMode.SIMULATOR,
        "job_type": ProductJobType.LIVE_MONITOR,
        "sample_count": 4,
        "monitor_sample_interval_seconds": 0.0,
        "monitor_max_buffer_points": 5,
    }
    values.update(changes)
    return ProductWorkflowConfiguration(**cast(Any, values))


def _write_live_replay(path: Path) -> None:
    path.write_text(
        """row_type,schema_version,dataset_id,record_id,raw_record_id,timestamp_utc,channel,value,unit,status,source,quality_flags,record_count
META,csv-replay.v1,live-replay,,,,,,,,,,
DATA,csv-replay.v1,live-replay,in-0,in-0,2026-01-01T00:00:00Z,afe.ch0.input,100,mV,VALID,SYNTHETIC,,
DATA,csv-replay.v1,live-replay,out-0,out-0,2026-01-01T00:00:00Z,afe.ch0.output,212,mV,VALID,SYNTHETIC,,
DATA,csv-replay.v1,live-replay,state-0,state-0,2026-01-01T00:00:00Z,afe.ch0.threshold,0,bool,VALID,SYNTHETIC,,
DATA,csv-replay.v1,live-replay,in-1,in-1,2026-01-01T00:00:00.1Z,afe.ch0.input,200,mV,VALID,SYNTHETIC,,
DATA,csv-replay.v1,live-replay,out-1,out-1,2026-01-01T00:00:00.1Z,afe.ch0.output,412,mV,VALID,SYNTHETIC,,
DATA,csv-replay.v1,live-replay,state-1,state-1,2026-01-01T00:00:00.1Z,afe.ch0.threshold,1,bool,VALID,SYNTHETIC,,
END,csv-replay.v1,live-replay,,,,,,,,,,6
""",
        encoding="utf-8",
    )


def _afe_capabilities(
    *,
    device_id: str = "afe-live-memory",
    adc_indices: tuple[int, ...] = (0,),
) -> bytes:
    messages: tuple[
        AfeCapabilityDevice | AfeCapabilityChannel | AfeCapabilityEnd, ...
    ] = (
        AfeCapabilityDevice(
            7,
            device_id,
            frozenset({DeviceCommand.READ_MEASUREMENT}),
        ),
        *(
            AfeCapabilityChannel(
                7,
                CapabilityChannelKind.ADC,
                index,
                0,
                3300,
                MeasurementUnit.MILLIVOLT,
            )
            for index in adc_indices
        ),
        AfeCapabilityEnd(7, len(adc_indices)),
    )
    return "".join(encode_afe_message(message) for message in messages).encode(
        "ascii"
    )


def _afe_telemetry(sequence: int, input_mv: int) -> bytes:
    return encode_afe_message(
        AfeTelemetry(sequence, sequence * 10, 0, input_mv, 2 * input_mv, 2000, 0, 0)
    ).encode("ascii")


def _damaged_crc(record: bytes) -> bytes:
    replacement = b"0000" if record[-5:-1] != b"0000" else b"FFFF"
    return record[:-5] + replacement + b"\n"


def test_live_monitor_simulator_product_chain_is_finite_and_bounded() -> None:
    prepared = prepare_product_job(_simulator_config(), "live-monitor-product")

    assert isinstance(prepared.live_monitor_session, LiveMonitorSession)
    assert isinstance(prepared.service_factory(prepared.request), LiveMonitorJobService)
    execution = execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
    )

    assert execution.worker_state is ProductWorkerState.SUCCEEDED
    assert execution.result is not None
    assert execution.result.status is ProductResultStatus.COMPLETED
    assert execution.result.test_run_outcome is None
    assert execution.result.evidence_source is EvidenceSource.SYNTHETIC
    assert execution.output is not None
    assert execution.output.result_export is None
    assert len(execution.output.read_result.measurements) == 12
    snapshot = execution.output.live_monitor
    assert snapshot is not None
    assert snapshot.schema_version == LIVE_MONITOR_SCHEMA_VERSION
    assert snapshot.total_points == 12
    assert snapshot.evicted_points == 7
    assert tuple(point.index for point in snapshot.points) == (8, 9, 10, 11, 12)
    assert snapshot.paused is False
    assert execution.dropped_event_count == 0
    assert any("finite sample cycles" in line for line in prepared.review_lines)
    assert any("no background acquisition" in line for line in prepared.review_lines)

    with pytest.raises(ProductRequestError, match="LiveMonitorSnapshot"):
        ProductServiceOutput(
            execution.output.read_result,
            live_monitor=cast(Any, object()),
        )
    with pytest.raises(ProductRequestError, match="point count"):
        ProductServiceOutput(
            execution.output.read_result,
            live_monitor=LiveMonitorSnapshot((), 0, 0, False, 0, 5.0, 0, 0, 0),
        )


def test_live_monitor_service_rejects_invalid_construction_and_job_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = SimulatorAdapter(SimulatorConfig())
    workflow = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                2,
            ),
        )
    )
    slot = ProductServiceOutputSlot()
    session = LiveMonitorSession()

    with pytest.raises(ProductRequestError, match="ReadWorkflowRequest"):
        LiveMonitorJobService(
            adapter,
            cast(Any, object()),
            ("Host-only test.",),
            slot,
            session,
            sample_interval_seconds=0.0,
        )
    with pytest.raises(ProductRequestError, match="ProductServiceOutputSlot"):
        LiveMonitorJobService(
            adapter,
            workflow,
            ("Host-only test.",),
            cast(Any, object()),
            session,
            sample_interval_seconds=0.0,
        )
    with pytest.raises(ProductRequestError, match="LiveMonitorSession"):
        LiveMonitorJobService(
            adapter,
            workflow,
            ("Host-only test.",),
            slot,
            cast(Any, object()),
            sample_interval_seconds=0.0,
        )

    unequal = ReadWorkflowRequest(
        (
            workflow.requirements[0],
            ChannelReadRequest(
                "afe.ch0.output",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                1,
            ),
        )
    )
    with pytest.raises(ProductRequestError, match="equal channel sample counts"):
        LiveMonitorJobService(
            adapter,
            unequal,
            ("Host-only test.",),
            slot,
            session,
            sample_interval_seconds=0.0,
        )

    service = LiveMonitorJobService(
        adapter,
        workflow,
        ("Host-only test.",),
        slot,
        session,
        sample_interval_seconds=0.0,
    )
    wrong_request = ProductJobRequest(
        "wrong-live-job",
        ProductSourceMode.SIMULATOR,
        ProductJobType.READ,
        "afe",
        "1",
    )
    with pytest.raises(ProductRequestError, match="LIVE_MONITOR job"):
        service.run(
            wrong_request,
            ProductCancellationToken(),
            lambda message, completed, total: None,
        )

    prepared = prepare_product_job(_simulator_config(sample_count=2), "bad-observer")
    observed_service = prepared.service_factory(prepared.request)

    def publish_invalid_measurement(*args: object, **kwargs: object) -> object:
        cast(Any, kwargs["on_measurement"])(0, object())
        raise AssertionError("invalid observer input must stop the service")

    monkeypatch.setattr(
        services_module,
        "run_streaming_read_workflow",
        publish_invalid_measurement,
    )
    with pytest.raises(ProductServiceError, match="invalid measurement"):
        observed_service.run(
            prepared.request,
            ProductCancellationToken(),
            lambda message, completed, total: None,
        )


def test_live_monitor_can_select_only_the_primary_trace() -> None:
    prepared = prepare_product_job(
        _simulator_config(
            monitor_include_secondary=False,
            monitor_include_state=False,
            monitor_max_buffer_points=10,
        ),
        "live-primary-only",
    )
    execution = execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
    )

    assert execution.output is not None
    assert len(execution.output.read_result.measurements) == 4
    assert execution.output.live_monitor is not None
    assert execution.output.live_monitor.evicted_points == 0
    assert {
        point.measurement.channel for point in execution.output.live_monitor.points
    } == {"afe.ch0.input"}


def test_live_monitor_csv_replay_preserves_replay_evidence(tmp_path: Path) -> None:
    replay = tmp_path / "live.csv"
    _write_live_replay(replay)
    prepared = prepare_product_job(
        ProductWorkflowConfiguration(
            ProductSourceMode.CSV_REPLAY,
            ProductJobType.LIVE_MONITOR,
            replay_path=replay,
            sample_count=2,
            monitor_sample_interval_seconds=0.0,
            monitor_max_buffer_points=10,
        ),
        "live-replay-product",
    )

    execution = execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
    )

    assert execution.result is not None
    assert execution.result.status is ProductResultStatus.COMPLETED
    assert execution.result.evidence_source is EvidenceSource.CSV_REPLAY
    assert execution.output is not None
    assert execution.output.live_monitor is not None
    assert execution.output.live_monitor.total_points == 6
    assert all(
        point.measurement.source is EvidenceSource.CSV_REPLAY
        for point in execution.output.live_monitor.points
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"operation": ReadOperation.DIGITAL}, "analog operation"),
        ({"unit": MeasurementUnit.BOOLEAN}, "require V or mV"),
        ({"monitor_sample_interval_seconds": -0.1}, "between 0 and"),
        ({"monitor_sample_interval_seconds": 61.0}, "between 0 and"),
        (
            {
                "sample_count": 57,
                "monitor_sample_interval_seconds": 1.0,
            },
            "requested duration",
        ),
        ({"monitor_time_window_seconds": 0.0}, "between"),
        ({"monitor_time_window_seconds": 3601.0}, "between"),
        ({"monitor_max_buffer_points": 0}, "between"),
        (
            {"monitor_max_buffer_points": MAX_LIVE_MONITOR_MAX_POINTS + 1},
            "between",
        ),
        ({"monitor_include_secondary": 1}, "must be boolean"),
        ({"monitor_include_state": "yes"}, "must be boolean"),
        ({"secondary_channel": "afe.ch0.input"}, "identities must be distinct"),
        ({"sample_count": 4_000}, "multiplied by enabled channels"),
    ],
)
def test_live_monitor_configuration_rejects_unbounded_or_ambiguous_inputs(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ProductRequestError, match=message):
        _simulator_config(**changes)


def test_prepared_job_enforces_live_session_pairing() -> None:
    read_prepared = prepare_product_job(
        ProductWorkflowConfiguration(
            ProductSourceMode.SIMULATOR,
            ProductJobType.READ,
        ),
        "ordinary-read",
    )
    with pytest.raises(ProductRequestError, match="only LIVE_MONITOR"):
        replace(read_prepared, live_monitor_session=LiveMonitorSession())

    live_prepared = prepare_product_job(_simulator_config(), "paired-live")
    with pytest.raises(ProductRequestError, match="LiveMonitorSession"):
        replace(live_prepared, live_monitor_session=cast(Any, object()))
    with pytest.raises(ProductRequestError, match="only LIVE_MONITOR"):
        replace(live_prepared, live_monitor_session=None)


def test_catalog_exposes_live_for_offline_and_receive_only_serial_sources() -> None:
    assert (
        ProductJobType.LIVE_MONITOR
        in get_product_source(ProductSourceMode.SIMULATOR).supported_jobs
    )
    assert (
        ProductJobType.LIVE_MONITOR
        in get_product_source(ProductSourceMode.CSV_REPLAY).supported_jobs
    )
    assert (
        ProductJobType.LIVE_MONITOR
        in get_product_source(ProductSourceMode.SERIAL_READ_ONLY).supported_jobs
    )


def test_serial_live_monitor_product_chain_is_deferred_bounded_and_receive_only() -> None:
    backend = MemorySerialBackend.scripted(
        reads=(
            _afe_capabilities(),
            _afe_telemetry(1, 500),
            _afe_telemetry(2, 600),
        )
    )
    config = ProductWorkflowConfiguration(
        ProductSourceMode.SERIAL_READ_ONLY,
        ProductJobType.LIVE_MONITOR,
        AFE_PROFILE_NAME,
        AFE_PROFILE_VERSION,
        sample_count=2,
        serial_config=SerialSourceConfig(
            "MEMORY:AFE:LIVE",
            read_timeout_seconds=0.01,
            max_polls_per_operation=2,
            evidence_source=EvidenceSource.HOST_TEST,
        ),
        confirm_read_only=True,
        monitor_sample_interval_seconds=0.0,
        monitor_max_buffer_points=10,
        monitor_include_secondary=False,
        monitor_include_state=False,
    )

    prepared = prepare_product_job(
        config,
        "serial-live-product",
        backend_factory=lambda: backend,
    )
    assert backend.open_calls == []
    assert any("Worst-case serial receive wait budget" in line for line in prepared.review_lines)

    execution = execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
    )

    assert execution.worker_state is ProductWorkerState.SUCCEEDED
    assert execution.result is not None
    assert execution.result.evidence_source is EvidenceSource.HOST_TEST
    assert execution.output is not None
    assert [value.value for value in execution.output.read_result.measurements] == [
        500.0,
        600.0,
    ]
    assert execution.output.live_monitor is not None
    assert execution.output.live_monitor.total_points == 2
    assert len(backend.open_calls) == 1
    assert len(backend.read_calls) == 3
    assert backend.close_calls == 1
    assert not hasattr(backend, "write_calls")


def test_serial_live_monitor_reports_unsupported_for_unadvertised_afe_output() -> None:
    backend = MemorySerialBackend.scripted(reads=(_afe_capabilities(),))
    config = ProductWorkflowConfiguration(
        ProductSourceMode.SERIAL_READ_ONLY,
        ProductJobType.LIVE_MONITOR,
        AFE_PROFILE_NAME,
        AFE_PROFILE_VERSION,
        sample_count=1,
        serial_config=SerialSourceConfig(
            "MEMORY:AFE:OUTPUT-GAP",
            read_timeout_seconds=0.01,
            max_polls_per_operation=1,
            evidence_source=EvidenceSource.HOST_TEST,
        ),
        confirm_read_only=True,
        monitor_sample_interval_seconds=0.0,
        monitor_include_secondary=True,
        monitor_include_state=False,
    )

    prepared = prepare_product_job(
        config,
        "serial-live-output-gap",
        backend_factory=lambda: backend,
    )
    execution = execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
    )

    assert execution.worker_state is ProductWorkerState.SUCCEEDED
    assert execution.result is not None
    assert execution.result.status is ProductResultStatus.UNSUPPORTED
    assert execution.output is not None
    assert execution.output.read_result.missing_requirements == (
        "analog-channel:afe.ch0.output",
    )
    assert execution.output.live_monitor is not None
    assert execution.output.live_monitor.total_points == 0
    assert len(backend.open_calls) == 1
    assert len(backend.read_calls) == 1
    assert backend.close_calls == 1
    assert not hasattr(backend, "write_calls")


def test_serial_live_monitor_pins_identity_and_maps_dual_afe_adc_traces() -> None:
    backend = MemorySerialBackend.scripted(
        reads=(
            _afe_capabilities(device_id="afe-dual-memory", adc_indices=(0, 1)),
            _afe_telemetry(1, 500),
            _afe_telemetry(2, 600),
        )
    )
    config = ProductWorkflowConfiguration(
        ProductSourceMode.SERIAL_READ_ONLY,
        ProductJobType.LIVE_MONITOR,
        AFE_PROFILE_NAME,
        AFE_PROFILE_VERSION,
        sample_count=2,
        serial_config=SerialSourceConfig(
            "MEMORY:AFE:DUAL",
            read_timeout_seconds=0.01,
            max_polls_per_operation=2,
            evidence_source=EvidenceSource.HOST_TEST,
            expected_device_id="afe-dual-memory",
            afe_adc_channel_aliases=(
                SerialChannelAlias("adc0", "afe.ch0.input"),
                SerialChannelAlias("adc1", "afe.ch0.output"),
            ),
        ),
        confirm_read_only=True,
        monitor_sample_interval_seconds=0.0,
        monitor_max_buffer_points=10,
        monitor_include_secondary=True,
        monitor_include_state=False,
    )

    prepared = prepare_product_job(
        config,
        "serial-live-dual",
        backend_factory=lambda: backend,
    )
    assert backend.open_calls == []
    assert any(
        "exact match required for afe-dual-memory" in line
        for line in prepared.review_lines
    )
    assert any(
        "adc0->afe.ch0.input, adc1->afe.ch0.output" in line
        for line in prepared.review_lines
    )

    execution = execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
    )

    assert execution.worker_state is ProductWorkerState.SUCCEEDED
    assert execution.output is not None
    read = execution.output.read_result
    assert read.capabilities.device_id == "afe-dual-memory"
    assert read.capabilities.adc_channels == (
        "afe.ch0.input",
        "afe.ch0.output",
    )
    assert [measurement.channel for measurement in read.measurements] == [
        "afe.ch0.input",
        "afe.ch0.output",
        "afe.ch0.input",
        "afe.ch0.output",
    ]
    assert [measurement.value for measurement in read.measurements] == [
        500.0,
        1000.0,
        600.0,
        1200.0,
    ]
    assert execution.output.live_monitor is not None
    assert execution.output.live_monitor.total_points == 4
    assert len(backend.open_calls) == 1
    assert len(backend.read_calls) == 3
    assert backend.close_calls == 1
    assert not hasattr(backend, "write_calls")


@pytest.mark.parametrize(
    ("expected_device_id", "aliases"),
    [
        ("different-device", ()),
        (
            "afe-dual-memory",
            (SerialChannelAlias("adc0", "afe.ch0.input"),),
        ),
    ],
)
def test_serial_live_monitor_rejects_identity_or_alias_contract_before_telemetry(
    expected_device_id: str,
    aliases: tuple[SerialChannelAlias, ...],
) -> None:
    backend = MemorySerialBackend.scripted(
        reads=(
            _afe_capabilities(device_id="afe-dual-memory", adc_indices=(0, 1)),
            _afe_telemetry(1, 500),
        )
    )
    config = ProductWorkflowConfiguration(
        ProductSourceMode.SERIAL_READ_ONLY,
        ProductJobType.LIVE_MONITOR,
        AFE_PROFILE_NAME,
        AFE_PROFILE_VERSION,
        sample_count=1,
        serial_config=SerialSourceConfig(
            "MEMORY:AFE:CONTRACT",
            read_timeout_seconds=0.01,
            max_polls_per_operation=1,
            evidence_source=EvidenceSource.HOST_TEST,
            expected_device_id=expected_device_id,
            afe_adc_channel_aliases=aliases,
        ),
        confirm_read_only=True,
        monitor_sample_interval_seconds=0.0,
        monitor_include_secondary=False,
        monitor_include_state=False,
    )
    prepared = prepare_product_job(
        config,
        "serial-live-contract-rejection",
        backend_factory=lambda: backend,
    )

    execution = execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
    )

    assert execution.worker_state is ProductWorkerState.FAILED
    assert execution.output is None
    assert execution.issue is not None
    assert len(backend.open_calls) == 1
    assert len(backend.read_calls) == 1
    assert backend.close_calls == 1
    assert not hasattr(backend, "write_calls")


def test_serial_live_monitor_skips_bad_crc_within_the_reviewed_poll_budget() -> None:
    first = _afe_telemetry(1, 500)
    backend = MemorySerialBackend.scripted(
        reads=(_afe_capabilities(), _damaged_crc(first), first)
    )
    config = ProductWorkflowConfiguration(
        ProductSourceMode.SERIAL_READ_ONLY,
        ProductJobType.LIVE_MONITOR,
        AFE_PROFILE_NAME,
        AFE_PROFILE_VERSION,
        sample_count=1,
        serial_config=SerialSourceConfig(
            "MEMORY:AFE:CRC",
            read_timeout_seconds=0.01,
            max_polls_per_operation=2,
            evidence_source=EvidenceSource.HOST_TEST,
        ),
        confirm_read_only=True,
        monitor_sample_interval_seconds=0.0,
        monitor_include_secondary=False,
        monitor_include_state=False,
    )

    prepared = prepare_product_job(
        config,
        "serial-live-crc",
        backend_factory=lambda: backend,
    )
    execution = execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
    )

    assert execution.worker_state is ProductWorkerState.SUCCEEDED
    assert execution.output is not None
    assert execution.output.read_result.measurements[0].value == 500.0
    assert len(backend.read_calls) == 3
    assert backend.close_calls == 1


@pytest.mark.parametrize(
    "terminal_read",
    (SerialBackendTimeout(), SerialBackendDisconnected()),
)
def test_serial_live_monitor_timeout_or_disconnect_fails_closed(
    terminal_read: object,
) -> None:
    backend = MemorySerialBackend.scripted(
        reads=(_afe_capabilities(), terminal_read)
    )
    config = ProductWorkflowConfiguration(
        ProductSourceMode.SERIAL_READ_ONLY,
        ProductJobType.LIVE_MONITOR,
        AFE_PROFILE_NAME,
        AFE_PROFILE_VERSION,
        sample_count=1,
        serial_config=SerialSourceConfig(
            "MEMORY:AFE:FAIL",
            read_timeout_seconds=0.01,
            max_polls_per_operation=1,
            evidence_source=EvidenceSource.HOST_TEST,
        ),
        confirm_read_only=True,
        monitor_sample_interval_seconds=0.0,
        monitor_include_secondary=False,
        monitor_include_state=False,
    )
    prepared = prepare_product_job(
        config,
        "serial-live-failure",
        backend_factory=lambda: backend,
    )

    execution = execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
    )

    assert execution.worker_state is ProductWorkerState.FAILED
    assert execution.output is None
    assert execution.issue is not None
    assert backend.close_calls == 1


def test_serial_live_monitor_cancellation_releases_the_owned_port() -> None:
    class BlockingAfterCapabilitiesBackend(MemorySerialBackend):
        def __init__(self) -> None:
            super().__init__()
            self.read_actions.extend(
                (_afe_capabilities(), _afe_telemetry(1, 500))
            )
            self.measurement_read_started = Event()
            self.release_measurement = Event()

        def read(self, max_bytes: int, timeout_seconds: float) -> bytes:
            if self.read_calls:
                self.measurement_read_started.set()
                assert self.release_measurement.wait(2.0)
            return super().read(max_bytes, timeout_seconds)

    backend = BlockingAfterCapabilitiesBackend()
    config = ProductWorkflowConfiguration(
        ProductSourceMode.SERIAL_READ_ONLY,
        ProductJobType.LIVE_MONITOR,
        AFE_PROFILE_NAME,
        AFE_PROFILE_VERSION,
        sample_count=2,
        serial_config=SerialSourceConfig(
            "MEMORY:AFE:CANCEL",
            read_timeout_seconds=0.01,
            max_polls_per_operation=2,
            evidence_source=EvidenceSource.HOST_TEST,
        ),
        confirm_read_only=True,
        monitor_sample_interval_seconds=0.0,
        monitor_include_secondary=False,
        monitor_include_state=False,
    )
    prepared = prepare_product_job(
        config,
        "serial-live-cancel",
        backend_factory=lambda: backend,
    )
    worker = ProductJobWorker(prepared.service_factory, join_timeout_s=2.0)

    try:
        worker.start(prepared.request)
        assert backend.measurement_read_started.wait(2.0)
        assert worker.request_cancel() is True
        backend.release_measurement.set()
        assert worker.join(2.0) is True
        assert worker.state is ProductWorkerState.CANCELLED
        assert prepared.output_slot.value is None
        assert backend.close_calls == 1
        assert not hasattr(backend, "write_calls")
    finally:
        backend.release_measurement.set()
        worker.close(2.0)


def test_serial_live_monitor_rejects_a_runtime_budget_over_55_seconds() -> None:
    with pytest.raises(ProductRequestError, match="serial live monitor worst-case"):
        ProductWorkflowConfiguration(
            ProductSourceMode.SERIAL_READ_ONLY,
            ProductJobType.LIVE_MONITOR,
            sample_count=20,
            serial_config=SerialSourceConfig(
                "MEMORY:SLOW",
                read_timeout_seconds=0.25,
                max_polls_per_operation=32,
            ),
            confirm_read_only=True,
            monitor_sample_interval_seconds=0.02,
            monitor_include_secondary=False,
            monitor_include_state=False,
        )


def test_live_monitor_cli_json_and_human_views_are_bounded_and_honest() -> None:
    dependencies = CliDependencies(job_id_factory=lambda: "live-cli")
    machine = io.StringIO()
    assert (
        main(
            [
                "simulate",
                "monitor",
                "--cycles",
                "4",
                "--sample-interval",
                "0",
                "--max-buffer-points",
                "5",
                "--json",
            ],
            stdout=machine,
            dependencies=dependencies,
        )
        == 0
    )
    document = json.loads(machine.getvalue())
    assert document["request"]["job_type"] == "LIVE_MONITOR"
    assert document["result"]["test_run_outcome"] is None
    assert document["result"]["evidence_source"] == "SYNTHETIC"
    assert document["result_export"] is None
    assert document["live_monitor"]["total_points"] == 12
    assert document["live_monitor"]["retained_points"] == 5
    assert document["live_monitor"]["evicted_points"] == 7
    assert len(document["live_monitor"]["points"]) == 5
    assert document["hardware_claim"] == "NO_PERFORMANCE_VALIDATION"

    human = io.StringIO()
    assert (
        main(
            [
                "simulate",
                "monitor",
                "--cycles",
                "2",
                "--sample-interval",
                "0",
                "--no-secondary",
                "--no-state",
            ],
            stdout=human,
            dependencies=dependencies,
        )
        == 0
    )
    text = human.getvalue()
    assert "Live monitor: 2 acquired; 2 retained" in text
    assert "Engineering outcome: none" in text
    assert "Hardware performance validation: NOT CLAIMED" in text
    assert MAX_LIVE_MONITOR_DURATION_SECONDS == 55.0
