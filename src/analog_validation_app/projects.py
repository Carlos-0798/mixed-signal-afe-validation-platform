"""Versioned local test projects, immutable run history, and comparisons."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Event, Lock
from typing import Any, TypeVar, cast

from analog_validation import (
    MAX_REPLAY_BYTES,
    EvidenceSource,
    MeasurementUnit,
    ReadOperation,
    TestRunOutcome,
    __version__,
)
from analog_validation.exports import (
    MAX_RESULT_EXPORT_BYTES,
    write_calibration_coefficients_json,
    write_result_export_json,
)

from .errors import (
    ProductProjectExistsError,
    ProductProjectFormatError,
    ProductProjectLimitError,
    ProductProjectPathError,
    ProductRequestError,
)
from .issues import UserIssueCode
from .models import (
    ProductJobEvent,
    ProductJobType,
    ProductResultStatus,
    ProductSourceMode,
    ProductWorkerState,
)
from .product_workflows import ProductWorkflowConfiguration, prepare_product_job
from .services import ProductJobExecution, execute_product_job

VALIDATION_PROJECT_SCHEMA_VERSION = "validation-project.v1"
VALIDATION_PRESET_SCHEMA_VERSION = "validation-preset.v1"
VALIDATION_RUN_RECORD_SCHEMA_VERSION = "validation-run-record.v1"
VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION = "validation-run-manifest.v1"
VALIDATION_RUN_MANIFEST_V2_SCHEMA_VERSION = "validation-run-manifest.v2"
VALIDATION_RUN_MANIFEST_SCHEMA_VERSION = "validation-run-manifest.v3"
VALIDATION_RUN_INPUT_ARTIFACT_SCHEMA_VERSION = "validation-run-input-artifact.v1"
VALIDATION_RUN_COMPARISON_SCHEMA_VERSION = "validation-run-comparison.v1"
VALIDATION_RUN_MANIFEST_FILENAME = "run-manifest.json"
VALIDATION_PROJECT_SNAPSHOT_FILENAME = "project.snapshot.json"

MAX_VALIDATION_PROJECT_BYTES = 1_048_576
MAX_VALIDATION_RUN_MANIFEST_BYTES = 1_048_576
MAX_VALIDATION_PRESETS = 32
MAX_VALIDATION_RUN_RECORDS = 32
MAX_VALIDATION_HISTORY_INPUTS = 64
MAX_VALIDATION_TEXT_CHARS = 256
MAX_VALIDATION_DESCRIPTION_CHARS = 2_048
MAX_VALIDATION_METRICS = 128

_SAFE_ID = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_INPUT_ARTIFACT = re.compile(
    r"inputs/[0-9]{2}-[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?\.csv"
)
_EnumT = TypeVar("_EnumT", bound=Enum)
Clock = Callable[[], datetime]


class ValidationBatchStatus(str, Enum):
    """Terminal disposition of one planned project batch."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class ValidationBatchPhase(str, Enum):
    """Observable lifecycle stage for a sequential project batch."""

    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    CANCELLING = "CANCELLING"
    FINALIZING = "FINALIZING"
    FINISHED = "FINISHED"


@dataclass(frozen=True, slots=True)
class ValidationBatchProgress:
    """One immutable, truthful batch progress snapshot."""

    run_id: str
    event_index: int
    phase: ValidationBatchPhase
    current_preset_id: str | None
    current_preset_number: int | None
    total_presets: int
    completed_presets: int
    batch_status: ValidationBatchStatus | None = None

    def __post_init__(self) -> None:
        _identifier("run_id", self.run_id)
        if (
            isinstance(self.event_index, bool)
            or not isinstance(self.event_index, int)
            or self.event_index <= 0
        ):
            raise ProductProjectFormatError("progress event_index must be positive")
        if not isinstance(self.phase, ValidationBatchPhase):
            raise ProductProjectFormatError("progress phase must be ValidationBatchPhase")
        total = _bounded_count(
            "progress total_presets", self.total_presets, MAX_VALIDATION_PRESETS
        )
        if total == 0:
            raise ProductProjectFormatError("progress total_presets must be positive")
        completed = _bounded_count(
            "progress completed_presets",
            self.completed_presets,
            MAX_VALIDATION_PRESETS,
        )
        if completed > total:
            raise ProductProjectFormatError(
                "progress completed_presets cannot exceed total_presets"
            )
        if (self.current_preset_id is None) != (
            self.current_preset_number is None
        ):
            raise ProductProjectFormatError(
                "progress current preset ID and number must be provided together"
            )
        if self.current_preset_id is not None:
            _identifier("progress current_preset_id", self.current_preset_id)
            number = _bounded_count(
                "progress current_preset_number",
                self.current_preset_number,
                MAX_VALIDATION_PRESETS,
            )
            if number == 0 or number > total:
                raise ProductProjectFormatError(
                    "progress current_preset_number must be within the batch"
                )
        if self.phase is ValidationBatchPhase.FINISHED:
            if self.current_preset_id is not None:
                raise ProductProjectFormatError(
                    "finished progress cannot name a current preset"
                )
            if not isinstance(self.batch_status, ValidationBatchStatus):
                raise ProductProjectFormatError(
                    "finished progress requires a batch status"
                )
        elif self.batch_status is not None:
            raise ProductProjectFormatError(
                "only finished progress may carry a batch status"
            )


class ValidationBatchCancellationToken:
    """Thread-safe cooperative cancellation request shared by batch owners."""

    def __init__(self) -> None:
        self._event = Event()
        self._lock = Lock()

    @property
    def is_cancellation_requested(self) -> bool:
        return self._event.is_set()

    def request_cancel(self) -> bool:
        with self._lock:
            if self._event.is_set():
                return False
            self._event.set()
            return True


ValidationBatchProgressReporter = Callable[[ValidationBatchProgress], None]


def _identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ProductProjectFormatError(
            f"{name} must be 1-64 lowercase letters, digits, dots, underscores, or hyphens"
        )
    return value


def _text(name: str, value: object, *, maximum: int = MAX_VALIDATION_TEXT_CHARS) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProductProjectFormatError(f"{name} must be non-empty stripped text")
    if len(value) > maximum:
        raise ProductProjectLimitError(f"{name} exceeds {maximum} characters")
    if not value.isprintable():
        raise ProductProjectFormatError(f"{name} must contain only printable text")
    return value


def _optional_text(
    name: str,
    value: object,
    *,
    maximum: int = MAX_VALIDATION_DESCRIPTION_CHARS,
) -> str:
    if not isinstance(value, str):
        raise ProductProjectFormatError(f"{name} must be text")
    if value and value != value.strip():
        raise ProductProjectFormatError(f"{name} must be stripped text")
    if len(value) > maximum:
        raise ProductProjectLimitError(f"{name} exceeds {maximum} characters")
    if not value.isprintable():
        raise ProductProjectFormatError(f"{name} must contain only printable text")
    return value


def _bounded_count(name: str, value: object, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ProductProjectFormatError(f"{name} must be between 0 and {maximum}")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProductProjectFormatError(f"{name} must be numeric")
    checked = float(value)
    if not math.isfinite(checked):
        raise ProductProjectFormatError(f"{name} must be finite")
    return checked


def _timestamp(name: str, value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ProductProjectFormatError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _enum(name: str, enum_type: type[_EnumT], value: object) -> _EnumT:
    if not isinstance(value, str):
        raise ProductProjectFormatError(f"{name} must be text")
    try:
        return enum_type(value)
    except ValueError as error:
        raise ProductProjectFormatError(f"{name} has an unsupported value") from error


def _object(name: str, value: object, keys: tuple[str, ...]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProductProjectFormatError(f"{name} must be an object")
    if set(value) != set(keys):
        raise ProductProjectFormatError(f"{name} fields do not match the schema")
    return cast(dict[str, object], value)


def _array(name: str, value: object, maximum: int) -> list[object]:
    if not isinstance(value, list):
        raise ProductProjectFormatError(f"{name} must be an array")
    if len(value) > maximum:
        raise ProductProjectLimitError(f"{name} exceeds {maximum} entries")
    return cast(list[object], value)


def _string_array(name: str, value: object, maximum: int) -> tuple[str, ...]:
    values = _array(name, value, maximum)
    if not all(isinstance(item, str) for item in values):
        raise ProductProjectFormatError(f"{name} must contain only strings")
    checked = tuple(_text(name, item, maximum=1_024) for item in values)
    if len(checked) != len(set(checked)):
        raise ProductProjectFormatError(f"{name} cannot contain duplicates")
    return checked


def _reject_constant(value: str) -> None:
    raise ProductProjectFormatError(f"unsupported JSON numeric constant: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ProductProjectFormatError(f"duplicate JSON field: {key}")
        document[key] = value
    return document


def _parse_json(text: str, *, maximum_bytes: int, label: str) -> object:
    if not isinstance(text, str):
        raise ProductProjectFormatError(f"{label} content must be text")
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ProductProjectFormatError(f"{label} must be valid UTF-8") from error
    if len(encoded) > maximum_bytes:
        raise ProductProjectLimitError(f"{label} exceeds its byte limit")
    if "\x00" in text:
        raise ProductProjectFormatError(f"{label} cannot contain NUL")
    try:
        return json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except ProductProjectFormatError:
        raise
    except (json.JSONDecodeError, RecursionError) as error:
        raise ProductProjectFormatError(f"{label} is not valid JSON") from error


def _document_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _path(value: str | os.PathLike[str], *, label: str) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        raise ProductProjectPathError(f"{label} must be path-like")
    try:
        path = Path(value)
    except (TypeError, ValueError, OSError) as error:
        raise ProductProjectPathError(f"{label} is invalid") from error
    if not path.name:
        raise ProductProjectPathError(f"{label} must identify a file or directory")
    return path


def _read_bounded(
    value: str | os.PathLike[str],
    *,
    maximum_bytes: int,
    label: str,
) -> str:
    path = _path(value, label=label)
    try:
        if not path.exists():
            raise ProductProjectPathError(f"{label} does not exist")
        if not path.is_file():
            raise ProductProjectPathError(f"{label} must be a regular file")
        if path.stat().st_size > maximum_bytes:
            raise ProductProjectLimitError(f"{label} exceeds its byte limit")
        payload = path.read_bytes()
    except (ProductProjectPathError, ProductProjectLimitError):
        raise
    except OSError as error:
        raise ProductProjectPathError(f"{label} could not be read") from error
    if len(payload) > maximum_bytes:
        raise ProductProjectLimitError(f"{label} exceeds its byte limit")
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProductProjectFormatError(f"{label} must contain UTF-8 text") from error


def _write_new_text(value: str | os.PathLike[str], text: str, *, label: str) -> Path:
    path = _path(value, label=label)
    try:
        if not path.parent.exists() or not path.parent.is_dir():
            raise ProductProjectPathError(f"{label} parent directory must exist")
        if path.exists():
            raise ProductProjectExistsError(f"{label} already exists")
    except (ProductProjectPathError, ProductProjectExistsError):
        raise
    except OSError as error:
        raise ProductProjectPathError(f"{label} cannot be prepared") from error
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise ProductProjectExistsError(f"{label} already exists") from error
        temporary.unlink()
    except ProductProjectExistsError:
        raise
    except (OSError, UnicodeEncodeError) as error:
        raise ProductProjectPathError(f"{label} could not be written") from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return path


def _safe_relative_path(base: Path, value: object, *, label: str) -> Path:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProductProjectFormatError(f"{label} must be non-empty relative text")
    relative = Path(value)
    if relative.is_absolute() or relative.drive:
        raise ProductProjectFormatError(f"{label} must be relative to the project")
    base_resolved = base.resolve()
    try:
        resolved = (base_resolved / relative).resolve()
        resolved.relative_to(base_resolved)
    except (OSError, ValueError) as error:
        raise ProductProjectFormatError(
            f"{label} must remain inside the project directory"
        ) from error
    return resolved


@dataclass(frozen=True, slots=True)
class ValidationPreset:
    """One named offline workflow configuration stored in a local project."""

    preset_id: str
    name: str
    configuration: ProductWorkflowConfiguration
    schema_version: str = VALIDATION_PRESET_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("preset_id", self.preset_id)
        _text("preset name", self.name)
        if not isinstance(self.configuration, ProductWorkflowConfiguration):
            raise ProductProjectFormatError(
                "preset configuration must be ProductWorkflowConfiguration"
            )
        if self.configuration.source_mode is ProductSourceMode.SERIAL_READ_ONLY:
            raise ProductProjectFormatError(
                "saved projects cannot contain Serial; real resources require a fresh explicit review"
            )
        if self.configuration.serial_config is not None:
            raise ProductProjectFormatError(
                "saved projects cannot persist serial connection settings"
            )
        if self.schema_version != VALIDATION_PRESET_SCHEMA_VERSION:
            raise ProductProjectFormatError(
                f"unsupported validation preset schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class ValidationProject:
    """An immutable bounded collection of reusable offline test presets."""

    project_id: str
    name: str
    description: str
    presets: tuple[ValidationPreset, ...]
    schema_version: str = VALIDATION_PROJECT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("project_id", self.project_id)
        _text("project name", self.name)
        _optional_text("project description", self.description)
        if not isinstance(self.presets, tuple) or not all(
            isinstance(preset, ValidationPreset) for preset in self.presets
        ):
            raise ProductProjectFormatError(
                "project presets must be a tuple of ValidationPreset values"
            )
        if not self.presets:
            raise ProductProjectFormatError("project must contain at least one preset")
        if len(self.presets) > MAX_VALIDATION_PRESETS:
            raise ProductProjectLimitError(
                f"project exceeds {MAX_VALIDATION_PRESETS} presets"
            )
        identities = tuple(preset.preset_id for preset in self.presets)
        if len(identities) != len(set(identities)):
            raise ProductProjectFormatError("project preset IDs must be unique")
        if self.schema_version != VALIDATION_PROJECT_SCHEMA_VERSION:
            raise ProductProjectFormatError(
                f"unsupported validation project schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class ProjectRunMetric:
    """One finite numeric value copied from a finalized run for comparison."""

    name: str
    value: float
    unit: str

    def __post_init__(self) -> None:
        _text("metric name", self.name)
        object.__setattr__(self, "value", _finite("metric value", self.value))
        _text("metric unit", self.unit)


@dataclass(frozen=True, slots=True)
class ProjectRunRecord:
    """One preset execution summarized without changing its evidence class."""

    preset_id: str
    job_id: str
    source_mode: ProductSourceMode
    job_type: ProductJobType
    configuration_sha256: str
    worker_state: ProductWorkerState
    product_status: ProductResultStatus | None
    engineering_outcome: TestRunOutcome | None
    evidence_source: EvidenceSource | None
    measurement_count: int
    metrics: tuple[ProjectRunMetric, ...]
    limitations: tuple[str, ...]
    issue_code: UserIssueCode | None = None
    result_artifact: str | None = None
    result_sha256: str | None = None
    coefficient_artifact: str | None = None
    coefficient_sha256: str | None = None
    schema_version: str = VALIDATION_RUN_RECORD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("preset_id", self.preset_id)
        _text("job_id", self.job_id)
        if not isinstance(self.source_mode, ProductSourceMode):
            raise ProductProjectFormatError("source_mode must be ProductSourceMode")
        if self.source_mode is ProductSourceMode.SERIAL_READ_ONLY:
            raise ProductProjectFormatError("project run records cannot claim Serial")
        if not isinstance(self.job_type, ProductJobType):
            raise ProductProjectFormatError("job_type must be ProductJobType")
        if (
            not isinstance(self.configuration_sha256, str)
            or _SHA256.fullmatch(self.configuration_sha256) is None
        ):
            raise ProductProjectFormatError("configuration_sha256 is invalid")
        if not isinstance(self.worker_state, ProductWorkerState) or not self.worker_state.is_terminal:
            raise ProductProjectFormatError("worker_state must be terminal")
        if self.product_status is not None and not isinstance(
            self.product_status, ProductResultStatus
        ):
            raise ProductProjectFormatError(
                "product_status must be ProductResultStatus or None"
            )
        if self.engineering_outcome is not None and not isinstance(
            self.engineering_outcome, TestRunOutcome
        ):
            raise ProductProjectFormatError(
                "engineering_outcome must be TestRunOutcome or None"
            )
        if self.evidence_source is not None and not isinstance(
            self.evidence_source, EvidenceSource
        ):
            raise ProductProjectFormatError(
                "evidence_source must be EvidenceSource or None"
            )
        _bounded_count("measurement_count", self.measurement_count, 100_000)
        if not isinstance(self.metrics, tuple) or not all(
            isinstance(metric, ProjectRunMetric) for metric in self.metrics
        ):
            raise ProductProjectFormatError(
                "metrics must be a tuple of ProjectRunMetric values"
            )
        if len(self.metrics) > MAX_VALIDATION_METRICS:
            raise ProductProjectLimitError(
                f"metrics exceeds {MAX_VALIDATION_METRICS} entries"
            )
        metric_keys = tuple((metric.name, metric.unit) for metric in self.metrics)
        if len(metric_keys) != len(set(metric_keys)):
            raise ProductProjectFormatError("metric name/unit pairs must be unique")
        if not isinstance(self.limitations, tuple):
            raise ProductProjectFormatError("limitations must be a tuple")
        for limitation in self.limitations:
            _text("limitation", limitation, maximum=1_024)
        if self.issue_code is not None and not isinstance(self.issue_code, UserIssueCode):
            raise ProductProjectFormatError("issue_code must be UserIssueCode or None")
        self._validate_artifact_pair(
            "result", self.result_artifact, self.result_sha256
        )
        self._validate_artifact_pair(
            "coefficient", self.coefficient_artifact, self.coefficient_sha256
        )
        if self.schema_version != VALIDATION_RUN_RECORD_SCHEMA_VERSION:
            raise ProductProjectFormatError(
                f"unsupported validation run record schema: {self.schema_version}"
            )

    @staticmethod
    def _validate_artifact_pair(
        label: str, artifact: str | None, digest: str | None
    ) -> None:
        if (artifact is None) != (digest is None):
            raise ProductProjectFormatError(
                f"{label} artifact and SHA-256 must be present together"
            )
        if artifact is None:
            return
        path = Path(artifact)
        if (
            not artifact
            or path.is_absolute()
            or path.drive
            or path.name != artifact
            or artifact in {".", ".."}
        ):
            raise ProductProjectFormatError(
                f"{label} artifact must be one relative filename"
            )
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise ProductProjectFormatError(f"{label} SHA-256 is invalid")


@dataclass(frozen=True, slots=True)
class ValidationRunInputArtifact:
    """One exact CSV Replay input copied into an immutable run directory."""

    preset_id: str
    source_mode: ProductSourceMode
    artifact: str
    size_bytes: int
    sha256: str
    schema_version: str = VALIDATION_RUN_INPUT_ARTIFACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("input artifact preset_id", self.preset_id)
        if self.source_mode is not ProductSourceMode.CSV_REPLAY:
            raise ProductProjectFormatError(
                "input artifact source_mode must be CSV_REPLAY"
            )
        if not isinstance(self.artifact, str) or _INPUT_ARTIFACT.fullmatch(
            self.artifact
        ) is None:
            raise ProductProjectFormatError(
                "input artifact must be one safe CSV path inside inputs"
            )
        _bounded_count("input artifact size_bytes", self.size_bytes, MAX_REPLAY_BYTES)
        if not isinstance(self.sha256, str) or _SHA256.fullmatch(self.sha256) is None:
            raise ProductProjectFormatError("input artifact SHA-256 is invalid")
        if self.schema_version != VALIDATION_RUN_INPUT_ARTIFACT_SCHEMA_VERSION:
            raise ProductProjectFormatError(
                f"unsupported validation run input artifact schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class ValidationRunManifest:
    """Immutable run history published beside create-new result artifacts."""

    project_id: str
    run_id: str
    software_version: str
    project_artifact: str
    project_sha256: str
    started_at: datetime
    completed_at: datetime
    records: tuple[ProjectRunRecord, ...]
    schema_version: str = VALIDATION_RUN_MANIFEST_SCHEMA_VERSION
    batch_status: ValidationBatchStatus | None = None
    planned_preset_ids: tuple[str, ...] = ()
    not_started_preset_ids: tuple[str, ...] = ()
    input_artifacts: tuple[ValidationRunInputArtifact, ...] = ()

    def __post_init__(self) -> None:
        _identifier("project_id", self.project_id)
        _identifier("run_id", self.run_id)
        _text("software_version", self.software_version)
        ProjectRunRecord._validate_artifact_pair(
            "project", self.project_artifact, self.project_sha256
        )
        if self.project_artifact != VALIDATION_PROJECT_SNAPSHOT_FILENAME:
            raise ProductProjectFormatError(
                "project artifact must use the versioned snapshot filename"
            )
        started = _timestamp("started_at", self.started_at)
        completed = _timestamp("completed_at", self.completed_at)
        if completed < started:
            raise ProductProjectFormatError("completed_at cannot precede started_at")
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "completed_at", completed)
        if not isinstance(self.records, tuple) or not all(
            isinstance(record, ProjectRunRecord) for record in self.records
        ):
            raise ProductProjectFormatError(
                "records must be a tuple of ProjectRunRecord values"
            )
        if len(self.records) > MAX_VALIDATION_RUN_RECORDS:
            raise ProductProjectLimitError(
                f"run manifest exceeds {MAX_VALIDATION_RUN_RECORDS} records"
            )
        preset_ids = tuple(record.preset_id for record in self.records)
        job_ids = tuple(record.job_id for record in self.records)
        if len(preset_ids) != len(set(preset_ids)):
            raise ProductProjectFormatError("run record preset IDs must be unique")
        if len(job_ids) != len(set(job_ids)):
            raise ProductProjectFormatError("run record job IDs must be unique")
        if self.schema_version not in {
            VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION,
            VALIDATION_RUN_MANIFEST_V2_SCHEMA_VERSION,
            VALIDATION_RUN_MANIFEST_SCHEMA_VERSION,
        }:
            raise ProductProjectFormatError(
                f"unsupported validation run manifest schema: {self.schema_version}"
            )
        if not isinstance(self.planned_preset_ids, tuple):
            raise ProductProjectFormatError("planned_preset_ids must be a tuple")
        if not isinstance(self.not_started_preset_ids, tuple):
            raise ProductProjectFormatError("not_started_preset_ids must be a tuple")
        planned = self.planned_preset_ids or (
            preset_ids + self.not_started_preset_ids
        )
        for preset_id in planned:
            _identifier("planned preset ID", preset_id)
        for preset_id in self.not_started_preset_ids:
            _identifier("not-started preset ID", preset_id)
        if not planned:
            raise ProductProjectFormatError(
                "run manifest must contain records or plan at least one preset"
            )
        if len(planned) > MAX_VALIDATION_PRESETS:
            raise ProductProjectLimitError(
                f"planned presets exceed {MAX_VALIDATION_PRESETS} entries"
            )
        if len(planned) != len(set(planned)):
            raise ProductProjectFormatError("planned preset IDs must be unique")
        if len(self.not_started_preset_ids) != len(
            set(self.not_started_preset_ids)
        ):
            raise ProductProjectFormatError("not-started preset IDs must be unique")
        object.__setattr__(self, "planned_preset_ids", planned)
        if not isinstance(self.input_artifacts, tuple) or not all(
            isinstance(artifact, ValidationRunInputArtifact)
            for artifact in self.input_artifacts
        ):
            raise ProductProjectFormatError(
                "input_artifacts must be ValidationRunInputArtifact values"
            )
        input_preset_ids = tuple(
            artifact.preset_id for artifact in self.input_artifacts
        )
        if len(input_preset_ids) != len(set(input_preset_ids)):
            raise ProductProjectFormatError(
                "input artifact preset IDs must be unique"
            )

        if self.schema_version == VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION:
            if not self.records:
                raise ProductProjectFormatError("v1 run manifest must contain records")
            if (
                self.batch_status is not None
                or self.not_started_preset_ids
                or self.input_artifacts
            ):
                raise ProductProjectFormatError(
                    "v1 run manifest cannot carry v2/v3 fields"
                )
            return
        if self.schema_version == VALIDATION_RUN_MANIFEST_V2_SCHEMA_VERSION:
            if self.input_artifacts:
                raise ProductProjectFormatError(
                    "v2 run manifest cannot carry v3 input artifacts"
                )
        else:
            expected_input_preset_ids = tuple(
                record.preset_id
                for record in self.records
                if record.source_mode is ProductSourceMode.CSV_REPLAY
            )
            if input_preset_ids != expected_input_preset_ids:
                raise ProductProjectFormatError(
                    "v3 input artifacts must match executed CSV Replay presets in order"
                )

        if preset_ids + self.not_started_preset_ids != planned:
            raise ProductProjectFormatError(
                "run record preset is absent from its planned order, or the order drifted"
            )
        has_error = any(
            record.worker_state is ProductWorkerState.FAILED
            or record.product_status is ProductResultStatus.ERROR
            for record in self.records
        )
        has_cancelled = any(
            record.worker_state is ProductWorkerState.CANCELLED
            or record.product_status is ProductResultStatus.CANCELLED
            for record in self.records
        )
        status = self.batch_status
        if status is None:
            if has_error:
                status = ValidationBatchStatus.ERROR
            elif has_cancelled:
                status = ValidationBatchStatus.CANCELLED
            else:
                status = ValidationBatchStatus.COMPLETE
            object.__setattr__(self, "batch_status", status)
        if not isinstance(status, ValidationBatchStatus):
            raise ProductProjectFormatError(
                "v2/v3 run manifest requires a ValidationBatchStatus"
            )
        if has_error and status is not ValidationBatchStatus.ERROR:
            raise ProductProjectFormatError("failed records require ERROR batch status")
        if has_cancelled and status not in {
            ValidationBatchStatus.CANCELLED,
            ValidationBatchStatus.ERROR,
        }:
            raise ProductProjectFormatError(
                "cancelled records require CANCELLED or ERROR batch status"
            )
        if status is ValidationBatchStatus.ERROR and not has_error:
            raise ProductProjectFormatError("ERROR batch status requires a failed record")
        if status is ValidationBatchStatus.CANCELLED and not (
            has_cancelled or self.not_started_preset_ids
        ):
            raise ProductProjectFormatError(
                "CANCELLED batch status requires cancelled or not-started work"
            )
        if status in {
            ValidationBatchStatus.COMPLETE,
            ValidationBatchStatus.PARTIAL,
        } and self.not_started_preset_ids:
            raise ProductProjectFormatError(
                "completed batch status cannot contain not-started presets"
            )

    @property
    def engineering_failures(self) -> int:
        return sum(
            record.engineering_outcome is TestRunOutcome.FAIL
            for record in self.records
        )

    @property
    def operational_failures(self) -> int:
        return sum(
            record.worker_state is not ProductWorkerState.SUCCEEDED
            or record.product_status
            in {
                ProductResultStatus.ERROR,
                ProductResultStatus.CANCELLED,
                ProductResultStatus.INCOMPLETE,
                ProductResultStatus.UNSUPPORTED,
            }
            for record in self.records
        )


@dataclass(frozen=True, slots=True)
class ProjectMetricDelta:
    """One left-to-right numeric metric comparison."""

    name: str
    unit: str
    left_value: float | None
    right_value: float | None

    def __post_init__(self) -> None:
        _text("metric name", self.name)
        _text("metric unit", self.unit)
        if self.left_value is not None:
            object.__setattr__(
                self, "left_value", _finite("left metric value", self.left_value)
            )
        if self.right_value is not None:
            object.__setattr__(
                self, "right_value", _finite("right metric value", self.right_value)
            )

    @property
    def delta(self) -> float | None:
        if self.left_value is None or self.right_value is None:
            return None
        return self.right_value - self.left_value

    @property
    def changed(self) -> bool:
        return self.left_value != self.right_value


@dataclass(frozen=True, slots=True)
class ProjectRunComparisonEntry:
    """Status, evidence, artifact, and metric changes for one preset."""

    preset_id: str
    left: ProjectRunRecord | None
    right: ProjectRunRecord | None
    metric_deltas: tuple[ProjectMetricDelta, ...]

    def __post_init__(self) -> None:
        _identifier("preset_id", self.preset_id)
        for name in ("left", "right"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, ProjectRunRecord):
                raise ProductProjectFormatError(
                    f"{name} must be ProjectRunRecord or None"
                )
            if value is not None and value.preset_id != self.preset_id:
                raise ProductProjectFormatError(
                    f"{name} record must match the comparison preset"
                )
        if self.left is None and self.right is None:
            raise ProductProjectFormatError("comparison entry requires a run record")
        if not isinstance(self.metric_deltas, tuple) or not all(
            isinstance(metric, ProjectMetricDelta) for metric in self.metric_deltas
        ):
            raise ProductProjectFormatError(
                "metric_deltas must contain ProjectMetricDelta values"
            )

    @staticmethod
    def _record_identity(record: ProjectRunRecord | None) -> tuple[object, ...] | None:
        if record is None:
            return None
        return (
            record.source_mode,
            record.job_type,
            record.configuration_sha256,
            record.worker_state,
            record.product_status,
            record.engineering_outcome,
            record.evidence_source,
            record.measurement_count,
            record.issue_code,
        )

    @property
    def changed(self) -> bool:
        return self._record_identity(self.left) != self._record_identity(
            self.right
        ) or any(metric.changed for metric in self.metric_deltas)


@dataclass(frozen=True, slots=True)
class ValidationRunComparison:
    """A pure comparison of two verified manifests from the same project."""

    project_id: str
    left_run_id: str
    right_run_id: str
    left_project_sha256: str
    right_project_sha256: str
    entries: tuple[ProjectRunComparisonEntry, ...]
    schema_version: str = VALIDATION_RUN_COMPARISON_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("project_id", self.project_id)
        _identifier("left_run_id", self.left_run_id)
        _identifier("right_run_id", self.right_run_id)
        for name in ("left_project_sha256", "right_project_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
                raise ProductProjectFormatError(f"{name} is invalid")
        if not isinstance(self.entries, tuple) or not self.entries:
            raise ProductProjectFormatError("comparison must contain entries")
        if not all(isinstance(entry, ProjectRunComparisonEntry) for entry in self.entries):
            raise ProductProjectFormatError(
                "entries must contain ProjectRunComparisonEntry values"
            )
        identities = tuple(entry.preset_id for entry in self.entries)
        if len(identities) != len(set(identities)):
            raise ProductProjectFormatError("comparison preset IDs must be unique")
        if self.schema_version != VALIDATION_RUN_COMPARISON_SCHEMA_VERSION:
            raise ProductProjectFormatError(
                f"unsupported validation comparison schema: {self.schema_version}"
            )

    @property
    def changed_entries(self) -> int:
        return sum(entry.changed for entry in self.entries)

    @property
    def project_changed(self) -> bool:
        return self.left_project_sha256 != self.right_project_sha256


_WORKFLOW_FIELDS = tuple(field.name for field in fields(ProductWorkflowConfiguration))


def _workflow_to_dict(
    configuration: ProductWorkflowConfiguration,
    *,
    project_directory: Path,
) -> dict[str, object]:
    values: dict[str, object] = {}
    for field_name in _WORKFLOW_FIELDS:
        value = getattr(configuration, field_name)
        if isinstance(value, Enum):
            values[field_name] = value.value
        elif field_name == "replay_path":
            if value is None:
                values[field_name] = None
            else:
                replay = cast(Path, value)
                resolved = (
                    replay.resolve()
                    if replay.is_absolute()
                    else (project_directory / replay).resolve()
                )
                try:
                    relative = resolved.relative_to(project_directory.resolve())
                except ValueError as error:
                    raise ProductProjectFormatError(
                        "replay_path must remain inside the project directory"
                    ) from error
                values[field_name] = relative.as_posix()
        elif field_name == "serial_config":
            if value is not None:
                raise ProductProjectFormatError(
                    "saved projects cannot persist serial connection settings"
                )
            values[field_name] = None
        elif value is None or isinstance(value, (str, bool, int, float)):
            values[field_name] = value
        else:  # pragma: no cover - future schema guard
            raise ProductProjectFormatError(
                f"workflow field {field_name} is not serializable"
            )
    return values


def _workflow_from_dict(
    value: object,
    *,
    project_directory: Path,
) -> ProductWorkflowConfiguration:
    document = _object("workflow configuration", value, _WORKFLOW_FIELDS)
    if document["serial_config"] is not None:
        raise ProductProjectFormatError(
            "saved projects cannot contain serial connection settings"
        )
    values: dict[str, Any] = dict(document)
    values["source_mode"] = _enum(
        "source_mode", ProductSourceMode, document["source_mode"]
    )
    values["job_type"] = _enum("job_type", ProductJobType, document["job_type"])
    values["operation"] = _enum("operation", ReadOperation, document["operation"])
    values["unit"] = _enum("unit", MeasurementUnit, document["unit"])
    replay_path = document["replay_path"]
    values["replay_path"] = (
        None
        if replay_path is None
        else _safe_relative_path(
            project_directory, replay_path, label="replay_path"
        )
    )
    values["serial_config"] = None
    try:
        return ProductWorkflowConfiguration(**values)
    except ProductRequestError as error:
        raise ProductProjectFormatError(
            "workflow configuration violates the product contract"
        ) from error


def validation_project_to_dict(
    project: ValidationProject,
    *,
    project_directory: Path,
) -> dict[str, object]:
    """Map a validated project to its exact portable JSON shape."""

    if not isinstance(project, ValidationProject):
        raise ProductProjectFormatError("project must be ValidationProject")
    return {
        "schema_version": project.schema_version,
        "project_id": project.project_id,
        "name": project.name,
        "description": project.description,
        "presets": [
            {
                "schema_version": preset.schema_version,
                "preset_id": preset.preset_id,
                "name": preset.name,
                "configuration": _workflow_to_dict(
                    preset.configuration,
                    project_directory=project_directory,
                ),
            }
            for preset in project.presets
        ],
    }


def validation_project_from_dict(
    value: object,
    *,
    project_directory: Path,
) -> ValidationProject:
    """Strictly rebuild one project without opening replay or hardware resources."""

    root = _object(
        "validation project",
        value,
        ("schema_version", "project_id", "name", "description", "presets"),
    )
    if root["schema_version"] != VALIDATION_PROJECT_SCHEMA_VERSION:
        raise ProductProjectFormatError(
            f"unsupported validation project schema: {root['schema_version']}"
        )
    presets: list[ValidationPreset] = []
    for raw in _array("presets", root["presets"], MAX_VALIDATION_PRESETS):
        item = _object(
            "validation preset",
            raw,
            ("schema_version", "preset_id", "name", "configuration"),
        )
        presets.append(
            ValidationPreset(
                _identifier("preset_id", item["preset_id"]),
                _text("preset name", item["name"]),
                _workflow_from_dict(
                    item["configuration"],
                    project_directory=project_directory,
                ),
                cast(str, item["schema_version"]),
            )
        )
    return ValidationProject(
        _identifier("project_id", root["project_id"]),
        _text("project name", root["name"]),
        _optional_text("project description", root["description"]),
        tuple(presets),
        cast(str, root["schema_version"]),
    )


def dump_validation_project(project: ValidationProject, *, path: Path) -> str:
    """Serialize a project deterministically with replay paths relative to it."""

    document = validation_project_to_dict(
        project, project_directory=path.parent.resolve()
    )
    return json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
    ) + "\n"


def write_validation_project(
    path: str | os.PathLike[str], project: ValidationProject
) -> Path:
    """Publish a new project file; existing files are never replaced."""

    destination = _path(path, label="project destination")
    text = dump_validation_project(project, path=destination)
    if len(text.encode("utf-8")) > MAX_VALIDATION_PROJECT_BYTES:
        raise ProductProjectLimitError("project JSON exceeds its byte limit")
    return _write_new_text(destination, text, label="project destination")


def load_validation_project(path: str | os.PathLike[str]) -> ValidationProject:
    """Load a strict bounded project without touching referenced replay files."""

    source = _path(path, label="project file")
    document = _parse_json(
        _read_bounded(
            source,
            maximum_bytes=MAX_VALIDATION_PROJECT_BYTES,
            label="project file",
        ),
        maximum_bytes=MAX_VALIDATION_PROJECT_BYTES,
        label="project JSON",
    )
    return validation_project_from_dict(
        document, project_directory=source.parent.resolve()
    )


def build_default_validation_project(
    project_id: str,
    name: str,
    description: str = "Offline reusable AFE validation presets.",
) -> ValidationProject:
    """Create the bounded software-only starter suite used by the product CLI."""

    source = ProductSourceMode.SIMULATOR
    return ValidationProject(
        project_id,
        name,
        description,
        (
            ValidationPreset(
                "read-default",
                "Read five synthetic input observations",
                ProductWorkflowConfiguration(source, ProductJobType.READ),
            ),
            ValidationPreset(
                "dc-default",
                "Evaluate a synthetic DC transfer sweep",
                ProductWorkflowConfiguration(
                    source, ProductJobType.DC_ANALYSIS, sample_count=24
                ),
            ),
            ValidationPreset(
                "hysteresis-default",
                "Evaluate synthetic Schmitt hysteresis",
                ProductWorkflowConfiguration(source, ProductJobType.HYSTERESIS_ANALYSIS),
            ),
            ValidationPreset(
                "calibration-default",
                "Fit and evaluate synthetic linear calibration",
                ProductWorkflowConfiguration(
                    source, ProductJobType.CALIBRATION_ANALYSIS, sample_count=12
                ),
            ),
            ValidationPreset(
                "frequency-default",
                "Evaluate a synthetic single-pole frequency response",
                ProductWorkflowConfiguration(
                    source, ProductJobType.FREQUENCY_RESPONSE_ANALYSIS
                ),
            ),
            ValidationPreset(
                "live-default",
                "Capture a bounded synthetic live-view snapshot",
                ProductWorkflowConfiguration(
                    source,
                    ProductJobType.LIVE_MONITOR,
                    sample_count=20,
                    monitor_sample_interval_seconds=0.0,
                    monitor_max_buffer_points=256,
                ),
            ),
        ),
    )


def _metrics(execution: ProductJobExecution) -> tuple[ProjectRunMetric, ...]:
    output = execution.output
    if output is None:
        return ()
    metrics = [
        ProjectRunMetric(
            "acquired_measurements", float(len(output.read_result.measurements)), "count"
        )
    ]
    if output.result_export is not None:
        for metric in output.result_export.metrics:
            value = metric.value
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                metrics.append(ProjectRunMetric(metric.name, float(value), metric.unit))
    if output.live_monitor is not None:
        metrics.extend(
            (
                ProjectRunMetric(
                    "live_retained_points",
                    float(len(output.live_monitor.points)),
                    "count",
                ),
                ProjectRunMetric(
                    "live_evicted_points",
                    float(output.live_monitor.evicted_points),
                    "count",
                ),
                ProjectRunMetric(
                    "live_invalid_points",
                    float(output.live_monitor.invalid_points),
                    "count",
                ),
            )
        )
    return tuple(metrics)


def _record_from_execution(
    preset: ValidationPreset,
    execution: ProductJobExecution,
    *,
    configuration_sha256: str,
    result_artifact: Path | None,
    coefficient_artifact: Path | None,
) -> ProjectRunRecord:
    result = execution.result
    output = execution.output
    return ProjectRunRecord(
        preset.preset_id,
        execution.request.job_id,
        execution.request.source_mode,
        execution.request.job_type,
        configuration_sha256,
        execution.worker_state,
        None if result is None else result.status,
        None if result is None else result.test_run_outcome,
        None if result is None else result.evidence_source,
        0 if output is None else len(output.read_result.measurements),
        _metrics(execution),
        () if result is None else result.limitations,
        None if execution.issue is None else execution.issue.code,
        None if result_artifact is None else result_artifact.name,
        None
        if result_artifact is None
        else hashlib.sha256(result_artifact.read_bytes()).hexdigest(),
        None if coefficient_artifact is None else coefficient_artifact.name,
        None
        if coefficient_artifact is None
        else hashlib.sha256(coefficient_artifact.read_bytes()).hexdigest(),
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _project_directory(value: str | os.PathLike[str] | None) -> Path:
    if value is None:
        return Path.cwd().resolve()
    if not isinstance(value, (str, os.PathLike)):
        raise ProductProjectPathError("project_directory must be path-like")
    try:
        directory = Path(value).resolve()
        if not directory.exists() or not directory.is_dir():
            raise ProductProjectPathError("project_directory must exist and be a directory")
    except ProductProjectPathError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise ProductProjectPathError("project_directory is invalid") from error
    return directory


def _selected_presets(
    project: ValidationProject, selected_preset_ids: Iterable[str]
) -> tuple[ValidationPreset, ...]:
    if isinstance(selected_preset_ids, (str, bytes)) or not isinstance(
        selected_preset_ids, Iterable
    ):
        raise ProductProjectFormatError("selected_preset_ids must be an iterable")
    requested = tuple(selected_preset_ids)
    if len(requested) > MAX_VALIDATION_PRESETS:
        raise ProductProjectLimitError(
            f"selected presets exceeds {MAX_VALIDATION_PRESETS} entries"
        )
    for value in requested:
        _identifier("selected preset ID", value)
    if len(requested) != len(set(requested)):
        raise ProductProjectFormatError("selected preset IDs cannot repeat")
    if not requested:
        return project.presets
    by_id = {preset.preset_id: preset for preset in project.presets}
    missing = tuple(value for value in requested if value not in by_id)
    if missing:
        raise ProductProjectFormatError(
            "selected preset is not present in the project: " + ", ".join(missing)
        )
    return tuple(by_id[value] for value in requested)


def validation_run_manifest_to_dict(
    manifest: ValidationRunManifest,
) -> dict[str, object]:
    """Serialize exact run lineage without recomputing engineering outcomes."""

    if not isinstance(manifest, ValidationRunManifest):
        raise ProductProjectFormatError("manifest must be ValidationRunManifest")
    summary: dict[str, object] = {
        "record_count": len(manifest.records),
        "engineering_failures": manifest.engineering_failures,
        "operational_failures": manifest.operational_failures,
        "hardware_validation": False,
    }
    document: dict[str, object] = {
        "schema_version": manifest.schema_version,
        "project_id": manifest.project_id,
        "run_id": manifest.run_id,
        "software_version": manifest.software_version,
        "project_artifact": manifest.project_artifact,
        "project_sha256": manifest.project_sha256,
        "started_at": manifest.started_at.isoformat(),
        "completed_at": manifest.completed_at.isoformat(),
        "summary": summary,
        "records": [
            {
                "schema_version": record.schema_version,
                "preset_id": record.preset_id,
                "job_id": record.job_id,
                "source_mode": record.source_mode.value,
                "job_type": record.job_type.value,
                "configuration_sha256": record.configuration_sha256,
                "worker_state": record.worker_state.value,
                "product_status": None
                if record.product_status is None
                else record.product_status.value,
                "engineering_outcome": None
                if record.engineering_outcome is None
                else record.engineering_outcome.value,
                "evidence_source": None
                if record.evidence_source is None
                else record.evidence_source.value,
                "measurement_count": record.measurement_count,
                "metrics": [
                    {"name": metric.name, "value": metric.value, "unit": metric.unit}
                    for metric in record.metrics
                ],
                "limitations": list(record.limitations),
                "issue_code": None
                if record.issue_code is None
                else record.issue_code.value,
                "result_artifact": record.result_artifact,
                "result_sha256": record.result_sha256,
                "coefficient_artifact": record.coefficient_artifact,
                "coefficient_sha256": record.coefficient_sha256,
            }
            for record in manifest.records
        ],
    }
    if manifest.schema_version in {
        VALIDATION_RUN_MANIFEST_V2_SCHEMA_VERSION,
        VALIDATION_RUN_MANIFEST_SCHEMA_VERSION,
    }:
        if manifest.batch_status is None:  # pragma: no cover - dataclass invariant
            raise ProductProjectFormatError(
                "v2/v3 run manifest is missing batch status"
            )
        document["batch_status"] = manifest.batch_status.value
        document["planned_preset_ids"] = list(manifest.planned_preset_ids)
        document["not_started_preset_ids"] = list(
            manifest.not_started_preset_ids
        )
        summary.update(
            {
                "planned_preset_count": len(manifest.planned_preset_ids),
                "completed_preset_count": len(manifest.records),
                "not_started_preset_count": len(
                    manifest.not_started_preset_ids
                ),
            }
        )
    if manifest.schema_version == VALIDATION_RUN_MANIFEST_SCHEMA_VERSION:
        document["input_artifacts"] = [
            {
                "schema_version": artifact.schema_version,
                "preset_id": artifact.preset_id,
                "source_mode": artifact.source_mode.value,
                "artifact": artifact.artifact,
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256,
            }
            for artifact in manifest.input_artifacts
        ]
        summary["input_artifact_count"] = len(manifest.input_artifacts)
    return document


def dump_validation_run_manifest(manifest: ValidationRunManifest) -> str:
    return json.dumps(
        validation_run_manifest_to_dict(manifest),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
    ) + "\n"


def _optional_enum(
    name: str, enum_type: type[_EnumT], value: object
) -> _EnumT | None:
    return None if value is None else _enum(name, enum_type, value)


def _optional_artifact(name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProductProjectFormatError(f"{name} must be text or null")
    return value


def _input_artifact_from_dict(value: object) -> ValidationRunInputArtifact:
    item = _object(
        "input artifact",
        value,
        (
            "schema_version",
            "preset_id",
            "source_mode",
            "artifact",
            "size_bytes",
            "sha256",
        ),
    )
    return ValidationRunInputArtifact(
        _identifier("input artifact preset_id", item["preset_id"]),
        _enum("input artifact source_mode", ProductSourceMode, item["source_mode"]),
        _text("input artifact", item["artifact"]),
        _bounded_count(
            "input artifact size_bytes", item["size_bytes"], MAX_REPLAY_BYTES
        ),
        _text("input artifact SHA-256", item["sha256"]),
        cast(str, item["schema_version"]),
    )


def validation_run_manifest_from_dict(value: object) -> ValidationRunManifest:
    """Strictly rebuild one immutable run-history manifest."""

    if not isinstance(value, dict):
        raise ProductProjectFormatError("validation run manifest must be an object")
    schema_version = value.get("schema_version")
    root_keys: tuple[str, ...]
    summary_keys: tuple[str, ...]
    if schema_version == VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION:
        root_keys = (
            "schema_version",
            "project_id",
            "run_id",
            "software_version",
            "project_artifact",
            "project_sha256",
            "started_at",
            "completed_at",
            "summary",
            "records",
        )
        summary_keys = (
            "record_count",
            "engineering_failures",
            "operational_failures",
            "hardware_validation",
        )
    elif schema_version in {
        VALIDATION_RUN_MANIFEST_V2_SCHEMA_VERSION,
        VALIDATION_RUN_MANIFEST_SCHEMA_VERSION,
    }:
        root_keys = (
            "schema_version",
            "project_id",
            "run_id",
            "software_version",
            "project_artifact",
            "project_sha256",
            "started_at",
            "completed_at",
            "summary",
            "records",
            "batch_status",
            "planned_preset_ids",
            "not_started_preset_ids",
        )
        summary_keys = (
            "record_count",
            "engineering_failures",
            "operational_failures",
            "hardware_validation",
            "planned_preset_count",
            "completed_preset_count",
            "not_started_preset_count",
        )
        if schema_version == VALIDATION_RUN_MANIFEST_SCHEMA_VERSION:
            root_keys += ("input_artifacts",)
            summary_keys += ("input_artifact_count",)
    else:
        raise ProductProjectFormatError(
            f"unsupported validation run manifest schema: {schema_version}"
        )
    root = _object(
        "validation run manifest",
        value,
        root_keys,
    )
    summary = _object(
        "run summary",
        root["summary"],
        summary_keys,
    )
    if summary["hardware_validation"] is not False:
        raise ProductProjectFormatError(
            "offline project run cannot claim hardware validation"
        )
    records: list[ProjectRunRecord] = []
    record_keys = (
        "schema_version",
        "preset_id",
        "job_id",
        "source_mode",
        "job_type",
        "configuration_sha256",
        "worker_state",
        "product_status",
        "engineering_outcome",
        "evidence_source",
        "measurement_count",
        "metrics",
        "limitations",
        "issue_code",
        "result_artifact",
        "result_sha256",
        "coefficient_artifact",
        "coefficient_sha256",
    )
    for raw in _array("records", root["records"], MAX_VALIDATION_RUN_RECORDS):
        item = _object("run record", raw, record_keys)
        metrics = tuple(
            ProjectRunMetric(
                _text(
                    "metric name",
                    _object("metric", metric, ("name", "value", "unit"))["name"],
                ),
                _finite(
                    "metric value",
                    _object("metric", metric, ("name", "value", "unit"))["value"],
                ),
                _text(
                    "metric unit",
                    _object("metric", metric, ("name", "value", "unit"))["unit"],
                ),
            )
            for metric in _array("metrics", item["metrics"], MAX_VALIDATION_METRICS)
        )
        records.append(
            ProjectRunRecord(
                _identifier("preset_id", item["preset_id"]),
                _text("job_id", item["job_id"]),
                _enum("source_mode", ProductSourceMode, item["source_mode"]),
                _enum("job_type", ProductJobType, item["job_type"]),
                _text("configuration_sha256", item["configuration_sha256"]),
                _enum("worker_state", ProductWorkerState, item["worker_state"]),
                _optional_enum(
                    "product_status", ProductResultStatus, item["product_status"]
                ),
                _optional_enum(
                    "engineering_outcome",
                    TestRunOutcome,
                    item["engineering_outcome"],
                ),
                _optional_enum(
                    "evidence_source", EvidenceSource, item["evidence_source"]
                ),
                _bounded_count("measurement_count", item["measurement_count"], 100_000),
                metrics,
                _string_array("limitations", item["limitations"], 64),
                _optional_enum("issue_code", UserIssueCode, item["issue_code"]),
                _optional_artifact("result_artifact", item["result_artifact"]),
                _optional_artifact("result_sha256", item["result_sha256"]),
                _optional_artifact(
                    "coefficient_artifact", item["coefficient_artifact"]
                ),
                _optional_artifact(
                    "coefficient_sha256", item["coefficient_sha256"]
                ),
                cast(str, item["schema_version"]),
            )
        )
    has_batch_state = schema_version in {
        VALIDATION_RUN_MANIFEST_V2_SCHEMA_VERSION,
        VALIDATION_RUN_MANIFEST_SCHEMA_VERSION,
    }
    input_artifacts: tuple[ValidationRunInputArtifact, ...] = ()
    if schema_version == VALIDATION_RUN_MANIFEST_SCHEMA_VERSION:
        input_artifacts = tuple(
            _input_artifact_from_dict(raw)
            for raw in _array(
                "input_artifacts",
                root["input_artifacts"],
                MAX_VALIDATION_RUN_RECORDS,
            )
        )
    manifest = ValidationRunManifest(
        _identifier("project_id", root["project_id"]),
        _identifier("run_id", root["run_id"]),
        _text("software_version", root["software_version"]),
        _text("project_artifact", root["project_artifact"]),
        _text("project_sha256", root["project_sha256"]),
        _parse_timestamp("started_at", root["started_at"]),
        _parse_timestamp("completed_at", root["completed_at"]),
        tuple(records),
        cast(str, root["schema_version"]),
        _enum("batch_status", ValidationBatchStatus, root["batch_status"])
        if has_batch_state
        else None,
        _string_array(
            "planned_preset_ids",
            root["planned_preset_ids"],
            MAX_VALIDATION_PRESETS,
        )
        if has_batch_state
        else tuple(record.preset_id for record in records),
        _string_array(
            "not_started_preset_ids",
            root["not_started_preset_ids"],
            MAX_VALIDATION_PRESETS,
        )
        if has_batch_state
        else (),
        input_artifacts,
    )
    if summary["record_count"] != len(manifest.records):
        raise ProductProjectFormatError("run summary record_count is inconsistent")
    if summary["engineering_failures"] != manifest.engineering_failures:
        raise ProductProjectFormatError(
            "run summary engineering_failures is inconsistent"
        )
    if summary["operational_failures"] != manifest.operational_failures:
        raise ProductProjectFormatError(
            "run summary operational_failures is inconsistent"
        )
    if has_batch_state:
        expected_counts = {
            "planned_preset_count": len(manifest.planned_preset_ids),
            "completed_preset_count": len(manifest.records),
            "not_started_preset_count": len(manifest.not_started_preset_ids),
        }
        for key, expected in expected_counts.items():
            if summary[key] != expected:
                raise ProductProjectFormatError(
                    f"run summary {key} is inconsistent"
                )
    if (
        schema_version == VALIDATION_RUN_MANIFEST_SCHEMA_VERSION
        and summary["input_artifact_count"] != len(manifest.input_artifacts)
    ):
        raise ProductProjectFormatError(
            "run summary input_artifact_count is inconsistent"
        )
    return manifest


def _parse_timestamp(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise ProductProjectFormatError(f"{name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ProductProjectFormatError(f"{name} is not valid ISO-8601") from error
    return _timestamp(name, parsed)


def _verify_project_snapshot_lineage(
    manifest_path: Path,
    manifest: ValidationRunManifest,
    payload: bytes,
) -> None:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProductProjectFormatError(
            "project artifact must contain UTF-8 text"
        ) from error
    document = _parse_json(
        text,
        maximum_bytes=MAX_VALIDATION_PROJECT_BYTES,
        label="project artifact JSON",
    )
    snapshot = validation_project_from_dict(
        document,
        project_directory=manifest_path.parent.resolve(),
    )
    if snapshot.project_id != manifest.project_id:
        raise ProductProjectFormatError(
            "run manifest project_id does not match the project snapshot"
        )
    root = _object(
        "validation project",
        document,
        ("schema_version", "project_id", "name", "description", "presets"),
    )
    configuration_hashes: dict[str, str] = {}
    snapshot_preset_ids: list[str] = []
    for raw in _array("presets", root["presets"], MAX_VALIDATION_PRESETS):
        item = _object(
            "validation preset",
            raw,
            ("schema_version", "preset_id", "name", "configuration"),
        )
        preset_id = cast(str, item["preset_id"])
        snapshot_preset_ids.append(preset_id)
        configuration_hashes[preset_id] = _document_sha256(
            item["configuration"]
        )
    missing_planned = (
        tuple(
            preset_id
            for preset_id in manifest.planned_preset_ids
            if preset_id not in configuration_hashes
        )
        if manifest.schema_version
        in {
            VALIDATION_RUN_MANIFEST_V2_SCHEMA_VERSION,
            VALIDATION_RUN_MANIFEST_SCHEMA_VERSION,
        }
        else ()
    )
    if missing_planned:
        raise ProductProjectFormatError(
            "planned preset is absent from the project snapshot: "
            + ", ".join(missing_planned)
        )
    all_snapshot_presets_planned = set(snapshot_preset_ids) == set(
        manifest.planned_preset_ids
    )
    if (
        manifest.batch_status is ValidationBatchStatus.COMPLETE
        and not all_snapshot_presets_planned
    ):
        raise ProductProjectFormatError(
            "COMPLETE batch must plan every project preset"
        )
    if (
        manifest.batch_status is ValidationBatchStatus.PARTIAL
        and all_snapshot_presets_planned
    ):
        raise ProductProjectFormatError(
            "PARTIAL batch must plan a strict project subset"
        )
    for record in manifest.records:
        expected = configuration_hashes.get(record.preset_id)
        if expected is None:
            raise ProductProjectFormatError(
                f"run record preset is absent from the project snapshot: {record.preset_id}"
            )
        if record.configuration_sha256 != expected:
            raise ProductProjectFormatError(
                "run record configuration SHA-256 does not match the project snapshot: "
                f"{record.preset_id}"
            )


def _verify_run_artifacts(manifest_path: Path, manifest: ValidationRunManifest) -> None:
    artifacts: list[tuple[str, str | None, str | None, int, int | None]] = [
        (
            "project",
            manifest.project_artifact,
            manifest.project_sha256,
            MAX_VALIDATION_PROJECT_BYTES,
            None,
        )
    ]
    for record in manifest.records:
        artifacts.extend(
            (
                (
                    "result",
                    record.result_artifact,
                    record.result_sha256,
                    MAX_RESULT_EXPORT_BYTES,
                    None,
                ),
                (
                    "coefficient",
                    record.coefficient_artifact,
                    record.coefficient_sha256,
                    MAX_RESULT_EXPORT_BYTES,
                    None,
                ),
            )
        )
    artifacts.extend(
        (
            "input",
            input_artifact.artifact,
            input_artifact.sha256,
            MAX_REPLAY_BYTES,
            input_artifact.size_bytes,
        )
        for input_artifact in manifest.input_artifacts
    )
    project_payload: bytes | None = None
    run_directory = manifest_path.parent.resolve()
    for label, name, expected, maximum_bytes, expected_size in artifacts:
        if name is None or expected is None:
            continue
        artifact = manifest_path.parent / name
        try:
            if not artifact.is_file():
                raise ProductProjectPathError(
                    f"{label} artifact is missing: {name}"
                )
            resolved_artifact = artifact.resolve(strict=True)
            try:
                resolved_artifact.relative_to(run_directory)
            except ValueError as error:
                raise ProductProjectPathError(
                    f"{label} artifact resolves outside the run directory: {name}"
                ) from error
            actual_size = resolved_artifact.stat().st_size
            if actual_size > maximum_bytes:
                raise ProductProjectLimitError(
                    f"{label} artifact exceeds its byte limit: {name}"
                )
            if expected_size is not None and actual_size != expected_size:
                raise ProductProjectFormatError(
                    f"{label} artifact byte size mismatch: {name}"
                )
            payload = resolved_artifact.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
        except (
            ProductProjectFormatError,
            ProductProjectPathError,
            ProductProjectLimitError,
        ):
            raise
        except OSError as error:
            raise ProductProjectPathError(
                f"{label} artifact could not be verified: {name}"
            ) from error
        if digest != expected:
            raise ProductProjectFormatError(
                f"{label} artifact SHA-256 mismatch: {name}"
            )
        if label == "project":
            project_payload = payload
    if project_payload is None:  # pragma: no cover - manifest invariant guard
        raise ProductProjectFormatError("project artifact could not be verified")
    _verify_project_snapshot_lineage(manifest_path, manifest, project_payload)


def load_validation_run_manifest(
    path: str | os.PathLike[str], *, verify_artifacts: bool = True
) -> ValidationRunManifest:
    """Load strict history and verify referenced artifact hashes by default."""

    if not isinstance(verify_artifacts, bool):
        raise ProductProjectFormatError("verify_artifacts must be boolean")
    source = _path(path, label="run manifest")
    manifest = validation_run_manifest_from_dict(
        _parse_json(
            _read_bounded(
                source,
                maximum_bytes=MAX_VALIDATION_RUN_MANIFEST_BYTES,
                label="run manifest",
            ),
            maximum_bytes=MAX_VALIDATION_RUN_MANIFEST_BYTES,
            label="run manifest JSON",
        )
    )
    if verify_artifacts:
        _verify_run_artifacts(source, manifest)
    return manifest


def _archive_replay_input(
    configuration: ProductWorkflowConfiguration,
    *,
    project_directory: Path,
    staging_directory: Path,
    preset_id: str,
    preset_number: int,
    archived_sources: dict[Path, tuple[str, int, str]],
) -> tuple[ProductWorkflowConfiguration, ValidationRunInputArtifact]:
    source_value = configuration.replay_path
    if source_value is None:  # pragma: no cover - configuration invariant
        raise ProductProjectFormatError("CSV Replay preset is missing replay_path")
    source = Path(source_value)
    if not source.is_absolute():
        source = project_directory / source
    try:
        resolved_source = source.resolve(strict=True)
        if not resolved_source.is_file():
            raise ProductProjectPathError("Replay input must be a regular file")
    except ProductProjectPathError:
        raise
    except (OSError, RuntimeError) as error:
        raise ProductProjectPathError(
            f"Replay input could not be archived for preset: {preset_id}"
        ) from error

    archived = archived_sources.get(resolved_source)
    if archived is None:
        relative_name = f"inputs/{preset_number:02d}-{preset_id}.csv"
        destination = staging_directory / relative_name
        try:
            destination.parent.mkdir(exist_ok=True)
            digest = hashlib.sha256()
            size_bytes = 0
            with resolved_source.open("rb") as source_stream, destination.open(
                "xb"
            ) as destination_stream:
                while chunk := source_stream.read(65_536):
                    size_bytes += len(chunk)
                    if size_bytes > MAX_REPLAY_BYTES:
                        raise ProductProjectLimitError(
                            f"Replay input exceeds its byte limit for preset: {preset_id}"
                        )
                    digest.update(chunk)
                    destination_stream.write(chunk)
            archived = (relative_name, size_bytes, digest.hexdigest())
            archived_sources[resolved_source] = archived
        except ProductProjectLimitError:
            destination.unlink(missing_ok=True)
            raise
        except OSError as error:
            destination.unlink(missing_ok=True)
            raise ProductProjectPathError(
                f"Replay input could not be archived for preset: {preset_id}"
            ) from error

    artifact_name, size_bytes, sha256 = archived
    archived_path = staging_directory / artifact_name
    return (
        replace(configuration, replay_path=archived_path),
        ValidationRunInputArtifact(
            preset_id,
            ProductSourceMode.CSV_REPLAY,
            artifact_name,
            size_bytes,
            sha256,
        ),
    )


def publish_validation_project_run(
    project: ValidationProject,
    output_directory: str | os.PathLike[str],
    run_id: str,
    *,
    selected_preset_ids: Iterable[str] = (),
    project_directory: str | os.PathLike[str] | None = None,
    clock: Clock = _now,
    cancellation: ValidationBatchCancellationToken | None = None,
    report_progress: ValidationBatchProgressReporter | None = None,
) -> ValidationRunManifest:
    """Run a bounded offline batch and atomically publish immutable history."""

    if not isinstance(project, ValidationProject):
        raise ProductProjectFormatError("project must be ValidationProject")
    _identifier("run_id", run_id)
    if not callable(clock):
        raise ProductProjectFormatError("clock must be callable")
    if cancellation is not None and not isinstance(
        cancellation, ValidationBatchCancellationToken
    ):
        raise ProductProjectFormatError(
            "cancellation must be ValidationBatchCancellationToken or None"
        )
    if report_progress is not None and not callable(report_progress):
        raise ProductProjectFormatError("report_progress must be callable or None")
    batch_cancellation = cancellation or ValidationBatchCancellationToken()
    project_base = _project_directory(project_directory)
    presets = _selected_presets(project, selected_preset_ids)
    project_document = validation_project_to_dict(
        project, project_directory=project_base
    )
    snapshot_text = json.dumps(
        project_document,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
    if len(snapshot_text.encode("utf-8")) > MAX_VALIDATION_PROJECT_BYTES:
        raise ProductProjectLimitError("project snapshot exceeds its byte limit")
    serialized_presets = cast(list[dict[str, object]], project_document["presets"])
    configuration_hashes = {
        cast(str, item["preset_id"]): _document_sha256(item["configuration"])
        for item in serialized_presets
    }
    target = _path(output_directory, label="run output directory")
    try:
        if not target.parent.exists() or not target.parent.is_dir():
            raise ProductProjectPathError(
                "run output parent directory must exist"
            )
        if target.exists():
            raise ProductProjectExistsError("run output directory already exists")
    except (ProductProjectPathError, ProductProjectExistsError):
        raise
    except OSError as error:
        raise ProductProjectPathError("run output directory cannot be prepared") from error

    started = _timestamp("clock result", clock())
    planned_preset_ids = tuple(preset.preset_id for preset in presets)
    all_project_preset_ids = tuple(preset.preset_id for preset in project.presets)
    total_presets = len(presets)
    progress_index = 0

    def emit_progress(
        phase: ValidationBatchPhase,
        *,
        current_preset_id: str | None = None,
        current_preset_number: int | None = None,
        completed_presets: int,
        batch_status: ValidationBatchStatus | None = None,
    ) -> None:
        nonlocal progress_index
        if report_progress is None:
            return
        progress_index += 1
        report_progress(
            ValidationBatchProgress(
                run_id,
                progress_index,
                phase,
                current_preset_id,
                current_preset_number,
                total_presets,
                completed_presets,
                batch_status,
            )
        )

    staging = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.", suffix=".staging", dir=target.parent)
    )
    published = False
    try:
        project_snapshot = staging / VALIDATION_PROJECT_SNAPSHOT_FILENAME
        project_snapshot.write_text(snapshot_text, encoding="utf-8", newline="\n")
        project_sha256 = hashlib.sha256(project_snapshot.read_bytes()).hexdigest()
        records: list[ProjectRunRecord] = []
        input_artifacts: list[ValidationRunInputArtifact] = []
        archived_sources: dict[Path, tuple[str, int, str]] = {}
        batch_status: ValidationBatchStatus | None = None
        for index, preset in enumerate(presets, start=1):
            emit_progress(
                ValidationBatchPhase.PREPARING,
                current_preset_id=preset.preset_id,
                current_preset_number=index,
                completed_presets=len(records),
            )
            if batch_cancellation.is_cancellation_requested:
                emit_progress(
                    ValidationBatchPhase.CANCELLING,
                    current_preset_id=preset.preset_id,
                    current_preset_number=index,
                    completed_presets=len(records),
                )
                batch_status = ValidationBatchStatus.CANCELLED
                break
            job_id = f"{run_id}-{index:02d}-{preset.preset_id}"
            run_configuration = preset.configuration
            if run_configuration.source_mode is ProductSourceMode.CSV_REPLAY:
                run_configuration, input_artifact = _archive_replay_input(
                    run_configuration,
                    project_directory=project_base,
                    staging_directory=staging,
                    preset_id=preset.preset_id,
                    preset_number=index,
                    archived_sources=archived_sources,
                )
                input_artifacts.append(input_artifact)
            prepared = prepare_product_job(
                run_configuration,
                job_id,
                prevalidate_replay=False,
                service_clock=clock,
            )
            join_timeout = 5.0
            if preset.configuration.job_type is ProductJobType.LIVE_MONITOR:
                join_timeout = min(
                    60.0,
                    max(
                        5.0,
                        preset.configuration.live_monitor_runtime_bound_seconds()
                        + 5.0,
                    ),
                )
            emit_progress(
                ValidationBatchPhase.RUNNING,
                current_preset_id=preset.preset_id,
                current_preset_number=index,
                completed_presets=len(records),
            )

            def report_worker_event(
                event: ProductJobEvent,
                *,
                current_preset_id: str = preset.preset_id,
                current_preset_number: int = index,
            ) -> None:
                phase = (
                    ValidationBatchPhase.CANCELLING
                    if event.state
                    in {
                        ProductWorkerState.CANCELLING,
                        ProductWorkerState.CANCELLED,
                    }
                    else ValidationBatchPhase.RUNNING
                )
                emit_progress(
                    phase,
                    current_preset_id=current_preset_id,
                    current_preset_number=current_preset_number,
                    completed_presets=len(records),
                )

            execution = execute_product_job(
                prepared.request,
                prepared.service_factory,
                prepared.output_slot,
                join_timeout_s=join_timeout,
                cancellation_requested=lambda: (
                    batch_cancellation.is_cancellation_requested
                ),
                report_event=report_worker_event
                if report_progress is not None
                else None,
            )
            result_artifact: Path | None = None
            coefficient_artifact: Path | None = None
            if execution.output is not None and execution.output.result_export is not None:
                result_artifact = staging / f"{index:02d}-{preset.preset_id}.result.json"
                write_result_export_json(
                    result_artifact, execution.output.result_export
                )
            if (
                execution.output is not None
                and execution.output.calibration_coefficients is not None
            ):
                coefficient_artifact = (
                    staging / f"{index:02d}-{preset.preset_id}.coefficients.json"
                )
                write_calibration_coefficients_json(
                    coefficient_artifact,
                    execution.output.calibration_coefficients,
                )
            records.append(
                _record_from_execution(
                    preset,
                    execution,
                    configuration_sha256=configuration_hashes[preset.preset_id],
                    result_artifact=result_artifact,
                    coefficient_artifact=coefficient_artifact,
                )
            )
            record = records[-1]
            if (
                record.worker_state is ProductWorkerState.FAILED
                or record.product_status is ProductResultStatus.ERROR
            ):
                batch_status = ValidationBatchStatus.ERROR
                break
            if (
                execution.interrupted
                or record.worker_state is ProductWorkerState.CANCELLED
                or record.product_status is ProductResultStatus.CANCELLED
            ):
                emit_progress(
                    ValidationBatchPhase.CANCELLING,
                    current_preset_id=preset.preset_id,
                    current_preset_number=index,
                    completed_presets=len(records),
                )
                batch_status = ValidationBatchStatus.CANCELLED
                break
            if (
                batch_cancellation.is_cancellation_requested
                and index < total_presets
            ):
                batch_status = ValidationBatchStatus.CANCELLED
                break
        if batch_status is None:
            batch_status = (
                ValidationBatchStatus.COMPLETE
                if set(planned_preset_ids) == set(all_project_preset_ids)
                else ValidationBatchStatus.PARTIAL
            )
        not_started_preset_ids = planned_preset_ids[len(records) :]
        emit_progress(
            ValidationBatchPhase.FINALIZING,
            completed_presets=len(records),
        )
        manifest = ValidationRunManifest(
            project.project_id,
            run_id,
            __version__,
            VALIDATION_PROJECT_SNAPSHOT_FILENAME,
            project_sha256,
            started,
            _timestamp("clock result", clock()),
            tuple(records),
            batch_status=batch_status,
            planned_preset_ids=planned_preset_ids,
            not_started_preset_ids=not_started_preset_ids,
            input_artifacts=tuple(input_artifacts),
        )
        manifest_text = dump_validation_run_manifest(manifest)
        if len(manifest_text.encode("utf-8")) > MAX_VALIDATION_RUN_MANIFEST_BYTES:
            raise ProductProjectLimitError("run manifest exceeds its byte limit")
        (staging / VALIDATION_RUN_MANIFEST_FILENAME).write_text(
            manifest_text, encoding="utf-8", newline="\n"
        )
        try:
            os.rename(staging, target)
        except FileExistsError as error:
            raise ProductProjectExistsError(
                "run output directory already exists"
            ) from error
        published = True
        emit_progress(
            ValidationBatchPhase.FINISHED,
            completed_presets=len(records),
            batch_status=batch_status,
        )
        return manifest
    except (ProductProjectExistsError, ProductProjectFormatError, ProductProjectLimitError, ProductProjectPathError):
        raise
    except OSError as error:
        raise ProductProjectPathError("run output could not be published") from error
    finally:
        if not published:
            shutil.rmtree(staging, ignore_errors=True)


def compare_validation_runs(
    left: ValidationRunManifest, right: ValidationRunManifest
) -> ValidationRunComparison:
    """Compare copied outcomes and metrics; never recalculate PASS or FAIL."""

    if not isinstance(left, ValidationRunManifest) or not isinstance(
        right, ValidationRunManifest
    ):
        raise ProductProjectFormatError(
            "left and right must be ValidationRunManifest values"
        )
    if left.project_id != right.project_id:
        raise ProductProjectFormatError("run manifests belong to different projects")
    left_records = {record.preset_id: record for record in left.records}
    right_records = {record.preset_id: record for record in right.records}
    order = tuple(
        dict.fromkeys(
            (*left_records.keys(), *right_records.keys())
        )
    )
    entries: list[ProjectRunComparisonEntry] = []
    for preset_id in order:
        left_record = left_records.get(preset_id)
        right_record = right_records.get(preset_id)
        left_metrics = (
            {}
            if left_record is None
            else {(metric.name, metric.unit): metric.value for metric in left_record.metrics}
        )
        right_metrics = (
            {}
            if right_record is None
            else {
                (metric.name, metric.unit): metric.value
                for metric in right_record.metrics
            }
        )
        keys = tuple(dict.fromkeys((*left_metrics.keys(), *right_metrics.keys())))
        deltas = tuple(
            ProjectMetricDelta(
                name,
                unit,
                left_metrics.get((name, unit)),
                right_metrics.get((name, unit)),
            )
            for name, unit in keys
        )
        entries.append(
            ProjectRunComparisonEntry(
                preset_id, left_record, right_record, deltas
            )
        )
    return ValidationRunComparison(
        left.project_id,
        left.run_id,
        right.run_id,
        left.project_sha256,
        right.project_sha256,
        tuple(entries),
    )


def validation_run_comparison_to_dict(
    comparison: ValidationRunComparison,
) -> dict[str, object]:
    """Map a pure run comparison to a stable presentation document."""

    if not isinstance(comparison, ValidationRunComparison):
        raise ProductProjectFormatError(
            "comparison must be ValidationRunComparison"
        )

    def summary(record: ProjectRunRecord | None) -> dict[str, object] | None:
        if record is None:
            return None
        return {
            "worker_state": record.worker_state.value,
            "product_status": None
            if record.product_status is None
            else record.product_status.value,
            "engineering_outcome": None
            if record.engineering_outcome is None
            else record.engineering_outcome.value,
            "evidence_source": None
            if record.evidence_source is None
            else record.evidence_source.value,
            "measurement_count": record.measurement_count,
            "issue_code": None
            if record.issue_code is None
            else record.issue_code.value,
            "result_sha256": record.result_sha256,
            "coefficient_sha256": record.coefficient_sha256,
        }

    return {
        "schema_version": comparison.schema_version,
        "project_id": comparison.project_id,
        "left_run_id": comparison.left_run_id,
        "right_run_id": comparison.right_run_id,
        "left_project_sha256": comparison.left_project_sha256,
        "right_project_sha256": comparison.right_project_sha256,
        "project_changed": comparison.project_changed,
        "changed_entries": comparison.changed_entries,
        "hardware_validation": False,
        "entries": [
            {
                "preset_id": entry.preset_id,
                "changed": entry.changed,
                "left": summary(entry.left),
                "right": summary(entry.right),
                "metric_deltas": [
                    {
                        "name": metric.name,
                        "unit": metric.unit,
                        "left_value": metric.left_value,
                        "right_value": metric.right_value,
                        "delta": metric.delta,
                        "changed": metric.changed,
                    }
                    for metric in entry.metric_deltas
                ],
            }
            for entry in comparison.entries
        ],
    }


__all__ = [
    "MAX_VALIDATION_HISTORY_INPUTS",
    "MAX_VALIDATION_PRESETS",
    "MAX_VALIDATION_PROJECT_BYTES",
    "MAX_VALIDATION_RUN_MANIFEST_BYTES",
    "MAX_VALIDATION_RUN_RECORDS",
    "VALIDATION_PRESET_SCHEMA_VERSION",
    "VALIDATION_PROJECT_SCHEMA_VERSION",
    "VALIDATION_PROJECT_SNAPSHOT_FILENAME",
    "VALIDATION_RUN_COMPARISON_SCHEMA_VERSION",
    "VALIDATION_RUN_INPUT_ARTIFACT_SCHEMA_VERSION",
    "VALIDATION_RUN_MANIFEST_FILENAME",
    "VALIDATION_RUN_MANIFEST_SCHEMA_VERSION",
    "VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION",
    "VALIDATION_RUN_MANIFEST_V2_SCHEMA_VERSION",
    "VALIDATION_RUN_RECORD_SCHEMA_VERSION",
    "ProjectMetricDelta",
    "ProjectRunComparisonEntry",
    "ProjectRunMetric",
    "ProjectRunRecord",
    "ValidationBatchCancellationToken",
    "ValidationBatchPhase",
    "ValidationBatchProgress",
    "ValidationBatchProgressReporter",
    "ValidationBatchStatus",
    "ValidationPreset",
    "ValidationProject",
    "ValidationRunComparison",
    "ValidationRunInputArtifact",
    "ValidationRunManifest",
    "build_default_validation_project",
    "compare_validation_runs",
    "dump_validation_project",
    "dump_validation_run_manifest",
    "load_validation_project",
    "load_validation_run_manifest",
    "publish_validation_project_run",
    "validation_project_from_dict",
    "validation_project_to_dict",
    "validation_run_comparison_to_dict",
    "validation_run_manifest_from_dict",
    "validation_run_manifest_to_dict",
    "write_validation_project",
]
