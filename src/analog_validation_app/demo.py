"""Atomic, deterministic, software-only portfolio demo publication."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from os import PathLike
from pathlib import Path, PurePosixPath

from analog_validation import (
    CSV_REPLAY_COLUMNS,
    CSV_REPLAY_SCHEMA_VERSION,
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
    TestRunOutcome,
    __version__,
    parse_csv_replay,
)
from analog_validation.exports import (
    dump_result_export_csv,
    dump_result_export_json,
)

from .errors import (
    ProductDemoExistsError,
    ProductDemoFormatError,
    ProductDemoPathError,
)
from .models import ProductJobType, ProductSourceMode, ProductWorkerState
from .presentation import REPORT_HARDWARE_CLAIM, build_human_report_view
from .product_workflows import ProductWorkflowConfiguration, prepare_product_job
from .reporting import publish_human_report
from .services import execute_product_job

PORTFOLIO_DEMO_SCHEMA_VERSION = "portfolio-demo.v1"
PORTFOLIO_DEMO_CONFIG_SCHEMA_VERSION = "portfolio-demo-config.v1"
PORTFOLIO_DEMO_JOB_ID = "portfolio-demo-dc-v1"
PORTFOLIO_DEMO_POINT_COUNT = 24
PORTFOLIO_DEMO_MANIFEST_FILENAME = "manifest.json"
PORTFOLIO_DEMO_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)

_MEDIA_TYPES = {
    ".csv": "text/csv; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".svg": "image/svg+xml; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class DemoArtifact:
    """One relative, content-addressed file in a demo publication."""

    relative_path: str
    media_type: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.relative_path, str) or not self.relative_path:
            raise ProductDemoFormatError("demo artifact path cannot be empty")
        path = PurePosixPath(self.relative_path)
        if path.is_absolute() or ".." in path.parts or str(path) != self.relative_path:
            raise ProductDemoFormatError(
                "demo artifact path must be a normalized relative POSIX path"
            )
        if not isinstance(self.media_type, str) or not self.media_type:
            raise ProductDemoFormatError("demo artifact media_type cannot be empty")
        if (
            isinstance(self.size_bytes, bool)
            or not isinstance(self.size_bytes, int)
            or self.size_bytes < 0
        ):
            raise ProductDemoFormatError(
                "demo artifact size_bytes must be non-negative"
            )
        if (
            not isinstance(self.sha256, str)
            or len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            raise ProductDemoFormatError(
                "demo artifact sha256 must contain 64 lowercase hex digits"
            )


@dataclass(frozen=True, slots=True)
class PortfolioDemoPublication:
    """Published demo identity; absolute paths stay outside committed artifacts."""

    output_directory: Path
    outcome: TestRunOutcome
    evidence_source: EvidenceSource
    canonical_result_sha256: str
    artifacts: tuple[DemoArtifact, ...]
    schema_version: str = PORTFOLIO_DEMO_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.output_directory, Path):
            raise ProductDemoFormatError("output_directory must be a Path")
        if not isinstance(self.outcome, TestRunOutcome):
            raise ProductDemoFormatError("outcome must be a TestRunOutcome")
        if not isinstance(self.evidence_source, EvidenceSource):
            raise ProductDemoFormatError("evidence_source must be an EvidenceSource")
        if (
            not isinstance(self.canonical_result_sha256, str)
            or len(self.canonical_result_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.canonical_result_sha256
            )
        ):
            raise ProductDemoFormatError(
                "canonical_result_sha256 must contain 64 lowercase hex digits"
            )
        if not isinstance(self.artifacts, tuple) or not self.artifacts:
            raise ProductDemoFormatError("demo artifacts cannot be empty")
        if not all(isinstance(value, DemoArtifact) for value in self.artifacts):
            raise ProductDemoFormatError("demo artifacts contain an invalid value")
        if len({value.relative_path for value in self.artifacts}) != len(
            self.artifacts
        ):
            raise ProductDemoFormatError("demo artifact paths cannot repeat")
        if self.schema_version != PORTFOLIO_DEMO_SCHEMA_VERSION:
            raise ProductDemoFormatError(
                f"unsupported portfolio demo schema: {self.schema_version}"
            )

    def artifact(self, relative_path: str) -> DemoArtifact:
        """Return one exact relative artifact descriptor."""

        selected = next(
            (
                artifact
                for artifact in self.artifacts
                if artifact.relative_path == relative_path
            ),
            None,
        )
        if selected is None:
            raise ProductDemoFormatError(f"demo artifact is absent: {relative_path}")
        return selected


@dataclass(frozen=True, slots=True)
class _ReplayValue:
    record_id: str
    raw_record_id: str
    timestamp_utc: str
    channel: str
    value: str
    unit: str
    status: str
    source: str
    quality_flags: str = ""


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _number(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if value == math.inf:
            return "Infinity"
        if value == -math.inf:
            return "-Infinity"
        return format(value, ".15g")
    raise ProductDemoFormatError("replay example value has an unsupported type")


def _quality_flags(measurement: Measurement) -> str:
    return "|".join(
        flag.value for flag in QualityFlag if flag in measurement.quality_flags
    )


def _measurement_replay_values(
    measurements: tuple[Measurement, ...],
) -> tuple[_ReplayValue, ...]:
    return tuple(
        _ReplayValue(
            f"demo-{measurement.record_id}",
            f"demo-{measurement.raw_record_id}",
            _timestamp(measurement.timestamp),
            measurement.channel,
            _number(measurement.value),
            measurement.unit.value,
            measurement.status.value,
            measurement.source.value,
            _quality_flags(measurement),
        )
        for measurement in sorted(
            measurements,
            key=lambda value: (value.timestamp, value.channel, value.record_id),
        )
    )


def _render_replay(dataset_id: str, values: tuple[_ReplayValue, ...]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CSV_REPLAY_COLUMNS)
    writer.writerow(
        ("META", CSV_REPLAY_SCHEMA_VERSION, dataset_id, *("" for _ in range(10)))
    )
    for value in values:
        writer.writerow(
            (
                "DATA",
                CSV_REPLAY_SCHEMA_VERSION,
                dataset_id,
                value.record_id,
                value.raw_record_id,
                value.timestamp_utc,
                value.channel,
                value.value,
                value.unit,
                value.status,
                value.source,
                value.quality_flags,
                "",
            )
        )
    writer.writerow(
        (
            "END",
            CSV_REPLAY_SCHEMA_VERSION,
            dataset_id,
            *("" for _ in range(9)),
            str(len(values)),
        )
    )
    payload = stream.getvalue().encode("utf-8")
    parsed = parse_csv_replay(payload)
    if parsed.dataset_id != dataset_id or len(parsed.records) != len(values):
        raise ProductDemoFormatError(
            "generated replay example failed its strict round-trip"
        )
    return payload


def _fault_replay() -> bytes:
    values = (
        _ReplayValue(
            "fault-input-valid",
            "synthetic-fault-input-valid",
            "2026-01-01T00:00:00.000000Z",
            "afe.ch0.input",
            "800",
            MeasurementUnit.MILLIVOLT.value,
            MeasurementStatus.VALID.value,
            EvidenceSource.SYNTHETIC.value,
        ),
        _ReplayValue(
            "fault-output-saturated",
            "synthetic-fault-output-saturated",
            "2026-01-01T00:00:00.100000Z",
            "afe.ch0.output",
            "3275",
            MeasurementUnit.MILLIVOLT.value,
            MeasurementStatus.SUSPECT.value,
            EvidenceSource.SYNTHETIC.value,
            QualityFlag.SATURATED.value,
        ),
        _ReplayValue(
            "fault-input-missing",
            "synthetic-fault-input-missing",
            "2026-01-01T00:00:00.200000Z",
            "afe.ch0.input",
            "",
            MeasurementUnit.MILLIVOLT.value,
            MeasurementStatus.INVALID.value,
            EvidenceSource.SYNTHETIC.value,
            f"{QualityFlag.MISSING.value}|{QualityFlag.COMMUNICATION_ERROR.value}",
        ),
        _ReplayValue(
            "fault-output-non-finite",
            "synthetic-fault-output-non-finite",
            "2026-01-01T00:00:00.300000Z",
            "afe.ch0.output",
            "NaN",
            MeasurementUnit.MILLIVOLT.value,
            MeasurementStatus.INVALID.value,
            EvidenceSource.SYNTHETIC.value,
            QualityFlag.NON_FINITE.value,
        ),
    )
    return _render_replay("portfolio-demo-faults-v1", values)


def _demo_configuration() -> bytes:
    document = {
        "schema_version": PORTFOLIO_DEMO_CONFIG_SCHEMA_VERSION,
        "source": {
            "mode": ProductSourceMode.SIMULATOR.value,
            "profile_name": "afe",
            "profile_version": "1",
            "evidence_source": EvidenceSource.SYNTHETIC.value,
        },
        "test": {
            "job_type": ProductJobType.DC_ANALYSIS.value,
            "job_id": PORTFOLIO_DEMO_JOB_ID,
            "input_channel": "afe.ch0.input",
            "output_channel": "afe.ch0.output",
            "points": PORTFOLIO_DEMO_POINT_COUNT,
            "unit": MeasurementUnit.MILLIVOLT.value,
        },
        "safety": {
            "output_permission": "DENIED",
            "serial_access": "NONE",
            "network_access": "NONE",
            "hardware_claim": REPORT_HARDWARE_CLAIM,
        },
        "reproducibility": {
            "fixed_run_time_utc": _timestamp(PORTFOLIO_DEMO_EPOCH),
            "create_new_output": True,
            "artifact_hash_algorithm": "SHA-256",
        },
    }
    return (
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _demo_readme() -> bytes:
    return f"""# Analog Validation Studio — Reproducible Software Demo

This directory was generated by `analog-validation demo` from the installed
package. The primary result is a deterministic {PORTFOLIO_DEMO_POINT_COUNT}-point
synthetic DC observation workflow followed by the product's formal offline
analysis, acceptance criteria, structured exports, and presentation-only report.

It did not drive a physical stimulus, open a serial port, access the network, or
measure analog hardware. `SYNTHETIC` PASS is a software result only.

## Inspect

- `result.json` and `result.csv`: the same finalized machine result.
- `report/report.html`: self-contained human report with no remote resources.
- `report/chart.svg`: deterministic chart copied from finalized values.
- `manifest.json`: SHA-256 identities and the evidence boundary.

## Replay examples

```text
analog-validation replay dc --input examples/replay-dc.csv --points {PORTFOLIO_DEMO_POINT_COUNT} --json
analog-validation replay read --input examples/replay-faults.csv --channel afe.ch0.input --samples 2 --json
```

The fault file intentionally contains saturated, missing, communication-error,
and non-finite synthetic records. It demonstrates fail-visible data handling; it
is not physical fault evidence.
""".encode()


def _output_path(value: str | PathLike[str]) -> Path:
    if not isinstance(value, (str, PathLike)):
        raise ProductDemoPathError("demo output must be a string or path-like value")
    try:
        path = Path(value)
    except (TypeError, ValueError, OSError) as error:
        raise ProductDemoPathError("demo output path is invalid") from error
    if not path.name:
        raise ProductDemoPathError("demo output must identify a new directory")
    return path


def _write_file(path: Path, payload: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise ProductDemoExistsError("demo staging file already exists") from error
    except OSError as error:
        raise ProductDemoPathError("demo artifact could not be written") from error


def _cleanup_staging(path: Path) -> None:
    try:
        if not path.exists():
            return
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                child.rmdir()
        path.rmdir()
    except OSError:
        pass


def _media_type(path: Path) -> str:
    selected = _MEDIA_TYPES.get(path.suffix.lower())
    if selected is None:
        raise ProductDemoFormatError(
            f"demo artifact has no reviewed media type: {path.name}"
        )
    return selected


def _artifact(root: Path, path: Path) -> DemoArtifact:
    relative = path.relative_to(root).as_posix()
    payload = path.read_bytes()
    return DemoArtifact(relative, _media_type(path), len(payload), _sha256(payload))


def _manifest(
    canonical_result_sha256: str,
    outcome: TestRunOutcome,
    evidence_source: EvidenceSource,
    limitations: tuple[str, ...],
    not_verified: tuple[str, ...],
    artifacts: tuple[DemoArtifact, ...],
) -> bytes:
    document = {
        "schema_version": PORTFOLIO_DEMO_SCHEMA_VERSION,
        "product": "Analog Validation Studio",
        "software_version": __version__,
        "workflow": {
            "source_mode": ProductSourceMode.SIMULATOR.value,
            "job_type": ProductJobType.DC_ANALYSIS.value,
            "job_id": PORTFOLIO_DEMO_JOB_ID,
            "point_count": PORTFOLIO_DEMO_POINT_COUNT,
            "output_permission": "DENIED",
        },
        "result": {
            "outcome": outcome.value,
            "evidence_source": evidence_source.value,
            "canonical_result_sha256": canonical_result_sha256,
        },
        "safety_and_privacy": {
            "hardware_claim": REPORT_HARDWARE_CLAIM,
            "serial_ports_opened": 0,
            "application_bytes_written": 0,
            "network_access": "NONE",
            "absolute_paths_embedded": False,
            "raw_serial_bytes_embedded": False,
        },
        "limitations": list(limitations),
        "not_verified": list(not_verified),
        "examples": {
            "replay": "examples/replay-dc.csv",
            "faults": "examples/replay-faults.csv",
            "declared_evidence": EvidenceSource.SYNTHETIC.value,
        },
        "artifact_hash_algorithm": "SHA-256",
        "artifact_count": len(artifacts),
        "artifacts": [
            {
                "relative_path": artifact.relative_path,
                "media_type": artifact.media_type,
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256,
            }
            for artifact in artifacts
        ],
    }
    return (
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def publish_portfolio_demo(
    output_directory: str | PathLike[str],
) -> PortfolioDemoPublication:
    """Run the reviewed synthetic chain and atomically publish exact artifacts."""

    destination = _output_path(output_directory)
    parent = destination.parent
    try:
        if not parent.exists() or not parent.is_dir():
            raise ProductDemoPathError(
                "demo output parent must be an existing directory"
            )
        if destination.exists() or destination.is_symlink():
            raise ProductDemoExistsError("demo output already exists")
    except (ProductDemoPathError, ProductDemoExistsError):
        raise
    except OSError as error:
        raise ProductDemoPathError("demo output cannot be prepared") from error

    config = ProductWorkflowConfiguration(
        ProductSourceMode.SIMULATOR,
        ProductJobType.DC_ANALYSIS,
        sample_count=PORTFOLIO_DEMO_POINT_COUNT,
    )
    prepared = prepare_product_job(
        config,
        PORTFOLIO_DEMO_JOB_ID,
        service_clock=lambda: PORTFOLIO_DEMO_EPOCH,
    )
    execution = execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
    )
    if (
        execution.worker_state is not ProductWorkerState.SUCCEEDED
        or execution.result is None
        or execution.result.test_run_outcome is not TestRunOutcome.PASS
        or execution.output is None
        or execution.output.result_export is None
    ):
        raise ProductDemoFormatError(
            "the fixed synthetic demo did not produce its reviewed PASS result"
        )
    bundle = execution.output.result_export
    view = build_human_report_view(bundle)
    if view.evidence_source is not EvidenceSource.SYNTHETIC:
        raise ProductDemoFormatError("the demo evidence source must remain SYNTHETIC")

    staging: Path | None = None
    try:
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=parent,
            )
        )
        staging_root = staging
        _write_file(staging_root / "README.md", _demo_readme())
        _write_file(staging_root / "demo-config.json", _demo_configuration())
        _write_file(
            staging_root / "result.json",
            dump_result_export_json(bundle).encode("utf-8"),
        )
        _write_file(
            staging_root / "result.csv",
            dump_result_export_csv(bundle).encode("utf-8"),
        )
        _write_file(
            staging_root / "examples" / "replay-dc.csv",
            _render_replay(
                "portfolio-demo-dc-v1",
                _measurement_replay_values(execution.output.read_result.measurements),
            ),
        )
        _write_file(
            staging_root / "examples" / "replay-faults.csv",
            _fault_replay(),
        )
        publish_human_report(staging_root / "report", view)

        paths = tuple(
            sorted(
                (path for path in staging_root.rglob("*") if path.is_file()),
                key=lambda path: path.relative_to(staging_root).as_posix(),
            )
        )
        artifacts = tuple(_artifact(staging_root, path) for path in paths)
        manifest_payload = _manifest(
            view.canonical_result_sha256,
            view.outcome,
            view.evidence_source,
            view.limitations,
            view.not_verified,
            artifacts,
        )
        manifest_path = staging_root / PORTFOLIO_DEMO_MANIFEST_FILENAME
        _write_file(manifest_path, manifest_payload)
        manifest_artifact = _artifact(staging_root, manifest_path)
        os.rename(staging_root, destination)
        staging = None
    except (ProductDemoExistsError, ProductDemoFormatError, ProductDemoPathError):
        raise
    except FileExistsError as error:
        raise ProductDemoExistsError("demo output already exists") from error
    except OSError as error:
        raise ProductDemoPathError("demo output could not be published") from error
    finally:
        if staging is not None:
            _cleanup_staging(staging)

    return PortfolioDemoPublication(
        destination.resolve(),
        view.outcome,
        view.evidence_source,
        view.canonical_result_sha256,
        (*artifacts, manifest_artifact),
    )


__all__ = [
    "PORTFOLIO_DEMO_CONFIG_SCHEMA_VERSION",
    "PORTFOLIO_DEMO_EPOCH",
    "PORTFOLIO_DEMO_JOB_ID",
    "PORTFOLIO_DEMO_MANIFEST_FILENAME",
    "PORTFOLIO_DEMO_POINT_COUNT",
    "PORTFOLIO_DEMO_SCHEMA_VERSION",
    "DemoArtifact",
    "PortfolioDemoPublication",
    "publish_portfolio_demo",
]
