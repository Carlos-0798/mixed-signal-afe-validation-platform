#!/usr/bin/env python3
"""Build and verify one privacy-minimal, host-only release candidate.

This tool never discovers or opens a serial port.  The optional serial package is
checked only with an injected host substitute named ``SYNTHETIC_PORT``.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any

from analog_validation import __version__

RELEASE_CANDIDATE_SCHEMA_VERSION = "release-candidate-manifest.v1"
PACKAGE_NAME = "mixed-signal-afe-validation-platform"
ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ADAPTER_EXAMPLE = (
    ROOT / "examples" / "public_adapter" / "read_only_voltage_adapter.py"
)
MAX_SDIST_MEMBERS = 10_000
MAX_SDIST_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
COMMAND_TIMEOUT_SECONDS = 1_800


class ReleaseCandidateError(RuntimeError):
    """Raised when a release gate fails without publishing a candidate."""


class ReleaseCandidateDestinationError(ReleaseCandidateError):
    """Raised when the create-new output boundary is not satisfied."""


@dataclass(frozen=True)
class ArtifactRecord:
    """Stable identity for one candidate distribution artifact."""

    filename: str
    kind: str
    size_bytes: int
    sha256: str

    def to_document(self) -> dict[str, object]:
        return {
            "filename": self.filename,
            "kind": self.kind,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(
    label: str,
    arguments: Sequence[str],
    *,
    cwd: Path = ROOT,
    environment: Mapping[str, str] | None = None,
    timeout: int = COMMAND_TIMEOUT_SECONDS,
    launch_attempts: int = 1,
) -> str:
    if launch_attempts < 1:
        raise ValueError("launch_attempts must be at least one")
    print(f"[RUN] {label}", flush=True)
    selected_environment = os.environ.copy()
    if environment is not None:
        selected_environment.update(environment)
    completed: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, launch_attempts + 1):
        try:
            completed = subprocess.run(
                list(arguments),
                cwd=cwd,
                env=selected_environment,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                timeout=timeout,
            )
            break
        except subprocess.TimeoutExpired as error:
            raise ReleaseCandidateError(f"{label} timed out") from error
        except OSError as error:
            if attempt == launch_attempts:
                error_name = type(error).__name__
                error_number = getattr(error, "winerror", None)
                suffix = f" ({error_name} {error_number})" if error_number else f" ({error_name})"
                raise ReleaseCandidateError(f"{label} could not start{suffix}") from error
            print(f"[RETRY] {label} after a transient launch error", flush=True)
            time.sleep(0.25)
    if completed is None:  # pragma: no cover - loop invariant
        raise ReleaseCandidateError(f"{label} did not start")
    if completed.returncode != 0:
        raise ReleaseCandidateError(
            f"{label} failed with exit code {completed.returncode}"
        )
    print(f"[PASS] {label}", flush=True)
    return completed.stdout


def _validate_output_destination(output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise ReleaseCandidateDestinationError(
            "candidate output already exists; choose a new directory"
        )
    if not output.parent.is_dir():
        raise ReleaseCandidateDestinationError(
            "candidate output parent must already exist"
        )
    if output.name in {"", ".", ".."}:
        raise ReleaseCandidateDestinationError("candidate output name is invalid")


def _source_identity() -> tuple[str, int]:
    status = _run(
        "clean Git working tree",
        ("git", "status", "--porcelain=v1", "--untracked-files=all"),
    )
    if status.strip():
        raise ReleaseCandidateError(
            "Git working tree is not clean; commit or intentionally remove pending changes"
        )
    commit = _run("source commit identity", ("git", "rev-parse", "HEAD")).strip()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ReleaseCandidateError("Git returned an invalid source commit identity")
    epoch_text = _run(
        "source commit timestamp", ("git", "show", "-s", "--format=%ct", "HEAD")
    ).strip()
    try:
        epoch = int(epoch_text)
    except ValueError as error:
        raise ReleaseCandidateError("Git returned an invalid source timestamp") from error
    if epoch < 0:
        raise ReleaseCandidateError("Git returned a negative source timestamp")
    return commit, epoch


def _safe_sdist_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or ".." in path.parts:
        raise ReleaseCandidateError("sdist contains an unsafe archive member")
    return path


def normalize_sdist(source: Path, destination: Path, source_epoch: int) -> None:
    """Rewrite generated sdist metadata deterministically without changing files."""

    if destination.exists() or destination.is_symlink():
        raise ReleaseCandidateDestinationError(
            "normalized sdist destination already exists"
        )
    members: list[tuple[str, bool, bytes]] = []
    total_size = 0
    try:
        with tarfile.open(source, mode="r:gz") as archive:
            archive_members = archive.getmembers()
            if len(archive_members) > MAX_SDIST_MEMBERS:
                raise ReleaseCandidateError("sdist contains too many archive members")
            for member in archive_members:
                _safe_sdist_member(member.name)
                if member.isdir():
                    members.append((member.name, True, b""))
                    continue
                if not member.isfile():
                    raise ReleaseCandidateError(
                        "sdist contains an unsupported non-file archive member"
                    )
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ReleaseCandidateError("sdist file member could not be read")
                payload = extracted.read()
                total_size += len(payload)
                if total_size > MAX_SDIST_UNCOMPRESSED_BYTES:
                    raise ReleaseCandidateError("sdist uncompressed content is too large")
                members.append((member.name, False, payload))
    except (OSError, tarfile.TarError) as error:
        raise ReleaseCandidateError("sdist archive could not be inspected") from error

    members.sort(key=lambda item: item[0])
    try:
        with destination.open("xb") as raw_output, gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=9,
            fileobj=raw_output,
            mtime=source_epoch,
        ) as compressed, tarfile.open(
            fileobj=compressed,
            mode="w",
            format=tarfile.PAX_FORMAT,
        ) as normalized:
            for name, is_directory, payload in members:
                info = tarfile.TarInfo(name)
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = source_epoch
                if is_directory:
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755
                    info.size = 0
                    normalized.addfile(info)
                else:
                    info.type = tarfile.REGTYPE
                    info.mode = 0o644
                    info.size = len(payload)
                    normalized.addfile(info, io.BytesIO(payload))
    except (OSError, tarfile.TarError) as error:
        destination.unlink(missing_ok=True)
        raise ReleaseCandidateError("normalized sdist could not be written") from error


def _artifact_records(directory: Path) -> tuple[ArtifactRecord, ...]:
    paths = sorted(path for path in directory.iterdir() if path.is_file())
    records: list[ArtifactRecord] = []
    for path in paths:
        if path.name.endswith(".whl"):
            kind = "wheel"
        elif path.name.endswith(".tar.gz"):
            kind = "sdist"
        else:
            raise ReleaseCandidateError("build produced an unexpected artifact")
        records.append(ArtifactRecord(path.name, kind, path.stat().st_size, _sha256(path)))
    if [record.kind for record in records].count("wheel") != 1:
        raise ReleaseCandidateError("build must produce exactly one wheel")
    if [record.kind for record in records].count("sdist") != 1:
        raise ReleaseCandidateError("build must produce exactly one sdist")
    return tuple(records)


def _validate_archives(directory: Path, records: Sequence[ArtifactRecord]) -> None:
    for record in records:
        path = directory / record.filename
        if record.kind == "wheel":
            try:
                with zipfile.ZipFile(path) as archive:
                    damaged = archive.testzip()
            except (OSError, zipfile.BadZipFile) as error:
                raise ReleaseCandidateError("wheel archive could not be inspected") from error
            if damaged is not None:
                raise ReleaseCandidateError("wheel archive contains a damaged member")
        else:
            try:
                with tarfile.open(path, mode="r:gz") as archive:
                    if not archive.getmembers():
                        raise ReleaseCandidateError("sdist archive is empty")
            except (OSError, tarfile.TarError) as error:
                raise ReleaseCandidateError("sdist archive could not be inspected") from error


def _build_once(directory: Path, source_epoch: int, label: str) -> tuple[ArtifactRecord, ...]:
    directory.mkdir()
    build_environment = {
        "PYTHONHASHSEED": "0",
        "SOURCE_DATE_EPOCH": str(source_epoch),
        "TZ": "UTC",
    }
    _run(
        label,
        (
            sys.executable,
            "-m",
            "build",
            "--sdist",
            "--wheel",
            "--outdir",
            str(directory),
        ),
        environment=build_environment,
        timeout=600,
    )
    sdist_paths = tuple(directory.glob("*.tar.gz"))
    if len(sdist_paths) != 1:
        raise ReleaseCandidateError("build must produce exactly one sdist before normalization")
    normalized = directory / ".normalized-sdist.tar.gz"
    normalize_sdist(sdist_paths[0], normalized, source_epoch)
    normalized.replace(sdist_paths[0])
    records = _artifact_records(directory)
    _validate_archives(directory, records)
    return records


def _compare_builds(
    first: Sequence[ArtifactRecord], second: Sequence[ArtifactRecord]
) -> None:
    if tuple(first) != tuple(second):
        raise ReleaseCandidateError(
            "independent builds are not byte-identical after metadata normalization"
        )


def _wheel_record(records: Sequence[ArtifactRecord]) -> ArtifactRecord:
    return next(record for record in records if record.kind == "wheel")


def _wheel_metadata(wheel: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(wheel) as archive:
            candidates = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            if len(candidates) != 1:
                raise ReleaseCandidateError(
                    "wheel must contain exactly one distribution metadata file"
                )
            document = BytesParser(policy=policy.default).parsebytes(
                archive.read(candidates[0])
            )
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ReleaseCandidateError("wheel metadata could not be read") from error

    name = str(document.get("Name", ""))
    version = str(document.get("Version", ""))
    requirements = tuple(str(value) for value in document.get_all("Requires-Dist", []))
    base_requirements = tuple(
        value for value in requirements if "extra ==" not in value.casefold()
    )
    serial_requirements = tuple(
        value
        for value in requirements
        if re.search(r"extra\s*==\s*['\"]serial['\"]", value, re.IGNORECASE)
    )
    if name != PACKAGE_NAME or version != __version__:
        raise ReleaseCandidateError("wheel name/version does not match the source package")
    if base_requirements:
        raise ReleaseCandidateError("base wheel unexpectedly declares dependencies")
    if len(serial_requirements) != 1 or not serial_requirements[0].casefold().startswith(
        "pyserial"
    ):
        raise ReleaseCandidateError("wheel serial extra does not match the reviewed boundary")
    return {
        "name": name,
        "version": version,
        "base_requirements": list(base_requirements),
        "serial_requirements": list(serial_requirements),
    }


def _venv_paths(root: Path) -> tuple[Path, Path]:
    if os.name == "nt":
        return root / "Scripts" / "python.exe", root / "Scripts" / "analog-validation.exe"
    return root / "bin" / "python", root / "bin" / "analog-validation"


def _tree_records(root: Path) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ReleaseCandidateError("installed demo contains a symbolic link")
        if path.is_file():
            records.append(
                {
                    "relative_path": path.relative_to(root).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    return tuple(records)


def _tree_sha256(records: Sequence[dict[str, object]]) -> str:
    canonical = json.dumps(
        list(records), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _load_json(text: str, label: str) -> dict[str, Any]:
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise ReleaseCandidateError(f"{label} did not return valid JSON") from error
    if not isinstance(document, dict):
        raise ReleaseCandidateError(f"{label} JSON must be an object")
    return document


def _verify_installed_demo(
    cli: Path,
    temporary_root: Path,
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    first_path = temporary_root / "demo-normal"
    second_path = temporary_root / "演示-beta"
    first_cli = _load_json(
        _run(
            "installed synthetic demo in normal path",
            (str(cli), "demo", "--output", str(first_path), "--json"),
            cwd=temporary_root,
            environment=environment,
            timeout=120,
            launch_attempts=3,
        ),
        "installed demo",
    )
    second_cli = _load_json(
        _run(
            "installed synthetic demo in Unicode path",
            (str(cli), "demo", "--output", str(second_path), "--json"),
            cwd=temporary_root,
            environment=environment,
            timeout=120,
            launch_attempts=3,
        ),
        "installed Unicode demo",
    )
    first_records = _tree_records(first_path)
    second_records = _tree_records(second_path)
    if first_records != second_records:
        raise ReleaseCandidateError("installed demos are not byte-identical")
    if first_cli.get("outcome") != "PASS" or second_cli.get("outcome") != "PASS":
        raise ReleaseCandidateError("installed demo did not report PASS")
    if first_cli.get("evidence_source") != "SYNTHETIC":
        raise ReleaseCandidateError("installed demo did not preserve SYNTHETIC evidence")
    if first_cli.get("hardware_claim") != "NO_NEW_HARDWARE_VALIDATION":
        raise ReleaseCandidateError("installed demo hardware boundary changed")
    manifest_path = first_path / "manifest.json"
    manifest = _load_json(manifest_path.read_text(encoding="utf-8"), "demo manifest")
    safety = manifest.get("safety_and_privacy")
    if not isinstance(safety, dict) or safety != {
        "absolute_paths_embedded": False,
        "application_bytes_written": 0,
        "hardware_claim": "NO_NEW_HARDWARE_VALIDATION",
        "network_access": "NONE",
        "raw_serial_bytes_embedded": False,
        "serial_ports_opened": 0,
    }:
        raise ReleaseCandidateError("installed demo safety/privacy contract changed")
    result = manifest.get("result")
    if not isinstance(result, dict):
        raise ReleaseCandidateError("demo manifest result is missing")
    canonical_result = result.get("canonical_result_sha256")
    if not isinstance(canonical_result, str) or re.fullmatch(
        r"[0-9a-f]{64}", canonical_result
    ) is None:
        raise ReleaseCandidateError("demo canonical result hash is invalid")
    return {
        "schema_version": manifest.get("schema_version"),
        "outcome": result.get("outcome"),
        "evidence_source": result.get("evidence_source"),
        "canonical_result_sha256": canonical_result,
        "artifact_count": len(first_records),
        "artifact_tree_sha256": _tree_sha256(first_records),
        "manifest_sha256": _sha256(manifest_path),
        "artifacts": list(first_records),
    }


def _verify_external_public_adapter(
    base_python: Path,
    temporary_root: Path,
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    if not PUBLIC_ADAPTER_EXAMPLE.is_file() or PUBLIC_ADAPTER_EXAMPLE.is_symlink():
        raise ReleaseCandidateError("public adapter example is missing or unsafe")
    external_root = temporary_root / "external-public-adapter"
    external_root.mkdir()
    external_example = external_root / PUBLIC_ADAPTER_EXAMPLE.name
    shutil.copyfile(PUBLIC_ADAPTER_EXAMPLE, external_example)
    document = _load_json(
        _run(
            "external public-API-only adapter",
            (str(base_python), "-I", str(external_example)),
            cwd=external_root,
            environment=environment,
            timeout=120,
            launch_attempts=3,
        ),
        "external public adapter",
    )
    expected: dict[str, object] = {
        "schema_version": "public-read-only-adapter-example.v1",
        "status": "COMPLETED",
        "evidence_source": "SYNTHETIC",
        "capabilities_read_only": True,
        "output_command_count": 0,
        "measurement_count": 3,
        "values_mv": [825.0, 830.0, 835.0],
        "connect_count": 1,
        "disconnect_count": 1,
        "connected_after_run": False,
        "application_bytes_written": 0,
    }
    if document != expected:
        raise ReleaseCandidateError("external public adapter contract changed")
    return document


def _clean_install_checks(
    wheel: Path, *, temporary_parent: Path
) -> dict[str, object]:
    """Verify fresh installs beside the requested output, then remove them.

    Some managed Windows hosts prohibit generated console launchers under the
    system temporary directory.  The candidate output parent is already an
    explicit writable destination, so using it keeps the launcher inside the
    caller-selected validation boundary without weakening the executable gate.
    """

    if not temporary_parent.is_dir():
        raise ReleaseCandidateError("clean-install temporary parent must exist")
    with tempfile.TemporaryDirectory(
        prefix="afe-release-install-", dir=temporary_parent
    ) as directory:
        temporary_root = Path(directory)
        base_root = temporary_root / "base"
        serial_root = temporary_root / "serial"
        clean_environment = {"PYTHONPATH": ""}
        _run(
            "create clean base environment",
            (sys.executable, "-m", "venv", str(base_root)),
            cwd=temporary_root,
            environment=clean_environment,
            timeout=300,
        )
        base_python, base_cli = _venv_paths(base_root)
        _run(
            "install base wheel without dependencies",
            (str(base_python), "-m", "pip", "install", "--no-deps", str(wheel)),
            cwd=temporary_root,
            environment=clean_environment,
            timeout=300,
        )
        _run(
            "check base dependencies",
            (str(base_python), "-m", "pip", "check"),
            cwd=temporary_root,
            environment=clean_environment,
        )
        _run(
            "verify headless base import boundary",
            (
                str(base_python),
                "-c",
                (
                    "import importlib.util,sys; import analog_validation_app; "
                    "assert importlib.util.find_spec('serial') is None; "
                    "assert 'tkinter' not in sys.modules"
                ),
            ),
            cwd=temporary_root,
            environment=clean_environment,
        )
        if not base_cli.is_file():
            raise ReleaseCandidateError("installed console entry point is missing")
        version_document = _load_json(
            _run(
                "installed CLI version",
                (str(base_cli), "version", "--json"),
                cwd=temporary_root,
                environment=clean_environment,
                launch_attempts=3,
            ),
            "installed version",
        )
        if version_document.get("software_version") != __version__:
            raise ReleaseCandidateError("installed CLI version does not match the candidate")
        demo = _verify_installed_demo(
            base_cli, temporary_root, environment=clean_environment
        )
        public_adapter = _verify_external_public_adapter(
            base_python, temporary_root, environment=clean_environment
        )

        _run(
            "create clean serial-extra environment",
            (sys.executable, "-m", "venv", str(serial_root)),
            cwd=temporary_root,
            environment=clean_environment,
            timeout=300,
        )
        serial_python, _ = _venv_paths(serial_root)
        _run(
            "install wheel with serial extra",
            (str(serial_python), "-m", "pip", "install", f"{wheel}[serial]"),
            cwd=temporary_root,
            environment=clean_environment,
            timeout=300,
        )
        _run(
            "check serial-extra dependencies",
            (str(serial_python), "-m", "pip", "check"),
            cwd=temporary_root,
            environment=clean_environment,
        )
        substitute_probe = (
            "from types import SimpleNamespace; "
            "from analog_validation_pyserial import PySerialBackend; "
            "backend=PySerialBackend(driver=object(), port_enumerator=lambda: "
            "(SimpleNamespace(device='SYNTHETIC_PORT', description='host substitute'),)); "
            "ports=backend.discover_ports(); "
            "assert len(ports)==1 and ports[0].port_id=='SYNTHETIC_PORT'; "
            "assert not hasattr(backend, 'write') and not backend.is_open"
        )
        _run(
            "verify injected serial substitute without physical discovery",
            (str(serial_python), "-c", substitute_probe),
            cwd=temporary_root,
            environment=clean_environment,
        )
    return {
        "base_install": "PASS",
        "base_runtime_dependencies": [],
        "base_pyserial_present": False,
        "base_tk_loaded": False,
        "serial_extra_install": "PASS",
        "serial_substitute": "INJECTED_HOST_ONLY",
        "physical_port_discovery": False,
        "physical_port_open": False,
        "application_write_surface": False,
        "demo": demo,
        "public_adapter": public_adapter,
    }


def _walk_manifest_strings(value: object) -> tuple[str, ...]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for key, nested in value.items():
            strings.append(str(key))
            strings.extend(_walk_manifest_strings(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            strings.extend(_walk_manifest_strings(nested))
    return tuple(strings)


def assert_manifest_privacy(document: Mapping[str, object]) -> None:
    """Reject path, identity, credential, physical-port, or raw-frame leakage."""

    strings = _walk_manifest_strings(document)
    usernames = {
        value.casefold()
        for name in ("USERNAME", "USER", "LOGNAME")
        if (value := os.environ.get(name)) and len(value) >= 3
    }
    for value in strings:
        folded = value.casefold()
        if re.match(r"^[a-z]:[\\/]", value, re.IGNORECASE):
            raise ReleaseCandidateError("release manifest contains an absolute path")
        if value.startswith(("/", "\\\\")):
            raise ReleaseCandidateError("release manifest contains an absolute path")
        if re.search(r"\bCOM\d+\b", value, re.IGNORECASE):
            raise ReleaseCandidateError("release manifest contains a physical port identifier")
        if re.search(r"(?:^|[\r\n])(?:TEL|AFE),", value):
            raise ReleaseCandidateError("release manifest contains a raw serial frame")
        if any(word in folded for word in ("password", "token", "api_key")):
            raise ReleaseCandidateError("release manifest contains a credential field")
        if not re.fullmatch(r"[0-9a-f]{40,64}", folded) and any(
            username in folded for username in usernames
        ):
            raise ReleaseCandidateError("release manifest contains a local username")


def _utc_timestamp(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def _manifest(
    *,
    commit: str,
    source_epoch: int,
    metadata: Mapping[str, Any],
    artifacts: Sequence[ArtifactRecord],
    install: Mapping[str, object],
) -> dict[str, object]:
    demo = install["demo"]
    if not isinstance(demo, dict):
        raise ReleaseCandidateError("installed demo evidence is missing")
    public_adapter = install["public_adapter"]
    if not isinstance(public_adapter, dict):
        raise ReleaseCandidateError("external public adapter evidence is missing")
    return {
        "schema_version": RELEASE_CANDIDATE_SCHEMA_VERSION,
        "candidate_status": "PASS",
        "package": {
            "name": metadata["name"],
            "version": metadata["version"],
        },
        "source": {
            "commit": commit,
            "commit_timestamp_utc": _utc_timestamp(source_epoch),
            "working_tree": "CLEAN",
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "system": platform.system(),
            "machine": platform.machine(),
        },
        "gates": {
            "tests_and_statement_coverage": "PASS",
            "ruff": "PASS",
            "mypy": "PASS",
            "development_dependency_check": "PASS",
            "independent_builds_byte_identical": "PASS",
            "archive_integrity": "PASS",
            "base_clean_install": install["base_install"],
            "serial_extra_clean_install": install["serial_extra_install"],
            "installed_demo_normal_and_unicode": "PASS",
            "external_public_adapter": "PASS",
            "manifest_privacy": "PASS",
        },
        "artifacts": [record.to_document() for record in artifacts],
        "dependency_boundaries": {
            "base_requires_dist": metadata["base_requirements"],
            "serial_extra_requires_dist": metadata["serial_requirements"],
            "base_pyserial_present": install["base_pyserial_present"],
            "base_tk_loaded": install["base_tk_loaded"],
            "serial_substitute": install["serial_substitute"],
            "physical_port_discovery": install["physical_port_discovery"],
            "application_write_surface": install["application_write_surface"],
        },
        "demo": demo,
        "public_adapter": public_adapter,
        "evidence_boundary": {
            "evidence_sources": ["HOST_TEST", "SYNTHETIC"],
            "hardware_claim": "NO_NEW_HARDWARE_VALIDATION",
            "afe_bench_requirements_verified": 0,
            "serial_ports_enumerated": 0,
            "serial_ports_opened": 0,
            "application_bytes_written": 0,
            "raw_serial_bytes_embedded": False,
            "physical_hardware_operations": "NOT_RUN",
        },
        "not_run": [
            "AFE hardware assembly or measurement",
            "ADC or DAC accuracy measurement",
            "physical serial-port discovery or open",
            "MSP430 reset, flash, command, or firmware identification",
            "laboratory instrument operation",
            "Git tag, GitHub Release, PyPI upload, or public publication",
        ],
    }


def _publish_candidate(
    output: Path,
    source_directory: Path,
    artifacts: Sequence[ArtifactRecord],
    document: Mapping[str, object],
) -> None:
    target = output.absolute()
    _validate_output_destination(target)
    candidate_names = [record.filename for record in artifacts]
    candidate_names.append("release-manifest.json")
    if os.name == "nt" and any(
        len(str(target / name)) >= 248 for name in candidate_names
    ):
        raise ReleaseCandidateDestinationError(
            "candidate output path is too long for a default Windows installation"
        )

    staging_root = Path(tempfile.mkdtemp(prefix=".rc-", dir=target.parent))
    published = False
    try:
        if os.name == "nt" and any(
            len(str(staging_root / name)) >= 260 for name in candidate_names
        ):
            raise ReleaseCandidateDestinationError(
                "candidate staging path is too long for a default Windows installation"
            )
        for record in artifacts:
            shutil.copyfile(
                source_directory / record.filename, staging_root / record.filename
            )
        manifest_path = staging_root / "release-manifest.json"
        with manifest_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2)
                + "\n"
            )
        staging_root.rename(target)
        published = True
    except ReleaseCandidateError:
        raise
    except OSError as error:
        raise ReleaseCandidateError(
            "candidate staging or atomic publication could not complete"
        ) from error
    finally:
        if not published:
            shutil.rmtree(staging_root, ignore_errors=True)


def _quality_gates() -> None:
    commands = (
        (
            "complete tests and 100% package statement coverage",
            (
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--cov=analog_validation",
                "--cov=analog_validation_app",
                "--cov=analog_validation_pyserial",
                "--cov-report=term-missing",
                "--cov-fail-under=100",
            ),
        ),
        (
            "Ruff static analysis",
            (
                sys.executable,
                "-m",
                "ruff",
                "check",
                "src",
                "tools",
                "tests",
                "examples/public_adapter",
            ),
        ),
        (
            "mypy type analysis",
            (
                sys.executable,
                "-m",
                "mypy",
                "src",
                "tools",
                "tests",
                "examples/public_adapter",
            ),
        ),
        (
            "development dependency consistency",
            (sys.executable, "-m", "pip", "check"),
        ),
    )
    for label, command in commands:
        _run(label, command)


def verify_release_candidate(output: Path) -> dict[str, object]:
    """Run all gates and atomically publish one new candidate directory."""

    _validate_output_destination(output)
    commit, source_epoch = _source_identity()
    _quality_gates()
    with tempfile.TemporaryDirectory(prefix="afe-release-build-") as build_directory:
        build_root = Path(build_directory)
        first_directory = build_root / "first"
        second_directory = build_root / "second"
        first = _build_once(first_directory, source_epoch, "isolated build one")
        second = _build_once(second_directory, source_epoch, "isolated build two")
        _compare_builds(first, second)
        wheel = first_directory / _wheel_record(first).filename
        metadata = _wheel_metadata(wheel)
        install = _clean_install_checks(wheel, temporary_parent=output.parent)
        final_status = _run(
            "final clean Git working tree",
            ("git", "status", "--porcelain=v1", "--untracked-files=all"),
        )
        if final_status.strip():
            raise ReleaseCandidateError("verification changed the Git working tree")
        document = _manifest(
            commit=commit,
            source_epoch=source_epoch,
            metadata=metadata,
            artifacts=first,
            install=install,
        )
        assert_manifest_privacy(document)

        _publish_candidate(output, first_directory, first, document)
    print(f"[PASS] release candidate created as {output.name}", flush=True)
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create one deterministic host-only release candidate."
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="new candidate directory; its parent must already exist",
    )
    arguments = parser.parse_args(argv)
    try:
        verify_release_candidate(arguments.output)
    except ReleaseCandidateDestinationError as error:
        print(f"RELEASE CANDIDATE NOT CREATED: {error}", file=sys.stderr)
        return 2
    except ReleaseCandidateError as error:
        print(f"RELEASE CANDIDATE FAILED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
