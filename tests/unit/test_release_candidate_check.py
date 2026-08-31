"""Release-candidate determinism, privacy, and create-new safety tests."""

from __future__ import annotations

import gzip
import io
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

import tools.release_candidate_check as release_module
from tools.release_candidate_check import (
    RELEASE_CANDIDATE_SCHEMA_VERSION,
    ArtifactRecord,
    ReleaseCandidateError,
    _compare_builds,
    _manifest,
    _publish_candidate,
    _run,
    _verify_external_public_adapter,
    assert_manifest_privacy,
    main,
    normalize_sdist,
)


def _write_sdist(
    path: Path,
    *,
    gzip_mtime: int,
    member_mtime: int,
    reverse_order: bool,
) -> None:
    members = [
        ("example-1.0", True, b""),
        ("example-1.0/README.md", False, b"deterministic content\n"),
        ("example-1.0/src/module.py", False, b"VALUE = 1\n"),
        ("example-1.0/src", True, b""),
    ]
    if reverse_order:
        members.reverse()
    with path.open("xb") as raw, gzip.GzipFile(
        filename=f"build-{gzip_mtime}.tar.gz",
        mode="wb",
        fileobj=raw,
        mtime=gzip_mtime,
    ) as compressed, tarfile.open(fileobj=compressed, mode="w") as archive:
        for name, is_directory, payload in members:
            info = tarfile.TarInfo(name)
            info.mtime = member_mtime
            info.uid = gzip_mtime
            info.gid = member_mtime
            info.uname = "private-builder"
            info.gname = "private-group"
            if is_directory:
                info.type = tarfile.DIRTYPE
                info.mode = 0o777
                archive.addfile(info)
            else:
                info.size = len(payload)
                info.mode = 0o600
                archive.addfile(info, io.BytesIO(payload))


def test_sdist_normalization_removes_build_time_order_and_owner_variance(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    normalized_first = tmp_path / "normalized-first.tar.gz"
    normalized_second = tmp_path / "normalized-second.tar.gz"
    epoch = 1_725_134_400
    _write_sdist(
        first, gzip_mtime=100, member_mtime=200, reverse_order=False
    )
    _write_sdist(
        second, gzip_mtime=300, member_mtime=400, reverse_order=True
    )

    normalize_sdist(first, normalized_first, epoch)
    normalize_sdist(second, normalized_second, epoch)

    assert normalized_first.read_bytes() == normalized_second.read_bytes()
    with tarfile.open(normalized_first, mode="r:gz") as archive:
        members = archive.getmembers()
    assert [member.name for member in members] == sorted(
        member.name for member in members
    )
    assert {member.mtime for member in members} == {epoch}
    assert {member.uid for member in members} == {0}
    assert {member.gid for member in members} == {0}
    assert {member.uname for member in members} == {""}
    assert {member.gname for member in members} == {""}


def test_sdist_normalization_rejects_path_traversal(tmp_path: Path) -> None:
    source = tmp_path / "unsafe.tar.gz"
    destination = tmp_path / "normalized.tar.gz"
    with tarfile.open(source, mode="w:gz") as archive:
        info = tarfile.TarInfo("../outside.txt")
        payload = b"unsafe"
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))

    with pytest.raises(ReleaseCandidateError, match="unsafe archive member"):
        normalize_sdist(source, destination, 1_725_134_400)
    assert not destination.exists()


def test_independent_build_comparison_requires_exact_artifact_identity() -> None:
    passing = (
        ArtifactRecord("package.whl", "wheel", 10, "a" * 64),
        ArtifactRecord("package.tar.gz", "sdist", 20, "b" * 64),
    )
    _compare_builds(passing, passing)

    changed = (
        ArtifactRecord("package.whl", "wheel", 10, "c" * 64),
        passing[1],
    )
    with pytest.raises(ReleaseCandidateError, match="not byte-identical"):
        _compare_builds(passing, changed)


def test_command_runner_retries_only_transient_launch_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    delays: list[float] = []

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("temporary launch block")
        return subprocess.CompletedProcess(["probe"], 0, "ready\n", "")

    monkeypatch.setattr(release_module.subprocess, "run", fake_run)
    monkeypatch.setattr(release_module.time, "sleep", delays.append)

    assert _run("transient probe", ("probe",), launch_attempts=2) == "ready\n"
    assert calls == 2
    assert delays == [0.25]


def test_external_public_adapter_runs_isolated_with_exact_read_only_result(
    tmp_path: Path,
) -> None:
    document = _verify_external_public_adapter(Path(sys.executable), tmp_path)

    assert document["status"] == "COMPLETED"
    assert document["evidence_source"] == "SYNTHETIC"
    assert document["capabilities_read_only"] is True
    assert document["output_command_count"] == 0
    assert document["application_bytes_written"] == 0
    assert document["connected_after_run"] is False


def _safe_manifest() -> dict[str, object]:
    return {
        "schema_version": RELEASE_CANDIDATE_SCHEMA_VERSION,
        "source": {"commit": "a" * 40},
        "artifact": {"filename": "package.whl", "sha256": "b" * 64},
        "hardware_claim": "NO_NEW_HARDWARE_VALIDATION",
    }


@pytest.mark.parametrize(
    "leak",
    (
        {"path": r"C:\Users\private\candidate.whl"},
        {"path": "/home/private/candidate.whl"},
        {"port": "COM17"},
        {"frame": "TEL,1,2,3"},
        {"token": "secret-value"},
        {"api_key": "secret-value"},
    ),
)
def test_manifest_privacy_rejects_sensitive_values(leak: dict[str, str]) -> None:
    document = _safe_manifest()
    document.update(leak)

    with pytest.raises(ReleaseCandidateError):
        assert_manifest_privacy(document)


def test_manifest_privacy_rejects_local_username(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("USERNAME", "private-builder")
    with pytest.raises(ReleaseCandidateError, match="username"):
        assert_manifest_privacy({"builder": "private-builder"})


def test_release_manifest_is_host_only_and_keeps_zero_hardware_claims() -> None:
    artifact = ArtifactRecord("package.whl", "wheel", 10, "a" * 64)
    install: dict[str, object] = {
        "base_install": "PASS",
        "serial_extra_install": "PASS",
        "base_pyserial_present": False,
        "base_tk_loaded": False,
        "serial_substitute": "INJECTED_HOST_ONLY",
        "physical_port_discovery": False,
        "application_write_surface": False,
        "public_adapter": {
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
        },
        "demo": {
            "outcome": "PASS",
            "evidence_source": "SYNTHETIC",
            "canonical_result_sha256": "b" * 64,
        },
    }
    document = _manifest(
        commit="c" * 40,
        source_epoch=1_725_134_400,
        metadata={
            "name": "mixed-signal-afe-validation-platform",
            "version": "0.1.0b1",
            "base_requirements": [],
            "serial_requirements": [
                'pyserial<4,>=3.5; extra == "serial"'
            ],
        },
        artifacts=(artifact,),
        install=install,
    )

    assert document["candidate_status"] == "PASS"
    gates = document["gates"]
    assert isinstance(gates, dict)
    assert gates["external_public_adapter"] == "PASS"
    assert document["public_adapter"] == install["public_adapter"]
    evidence = document["evidence_boundary"]
    assert isinstance(evidence, dict)
    assert evidence["evidence_sources"] == ["HOST_TEST", "SYNTHETIC"]
    assert evidence["hardware_claim"] == "NO_NEW_HARDWARE_VALIDATION"
    assert evidence["afe_bench_requirements_verified"] == 0
    assert evidence["serial_ports_enumerated"] == 0
    assert evidence["serial_ports_opened"] == 0
    assert evidence["application_bytes_written"] == 0
    assert_manifest_privacy(document)


def test_cli_refuses_to_overwrite_existing_candidate(tmp_path: Path) -> None:
    existing = tmp_path / "candidate"
    existing.mkdir()

    assert main(["--output", str(existing)]) == 2


def test_candidate_publication_uses_one_create_new_atomic_directory(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    wheel = source / "package.whl"
    sdist = source / "package.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    artifacts = (
        ArtifactRecord("package.whl", "wheel", 5, "a" * 64),
        ArtifactRecord("package.tar.gz", "sdist", 5, "b" * 64),
    )
    output = tmp_path / "candidate"
    document = _safe_manifest()

    _publish_candidate(output, source, artifacts, document)

    assert {path.name for path in output.iterdir()} == {
        "package.whl",
        "package.tar.gz",
        "release-manifest.json",
    }
    assert wheel.read_bytes() == (output / "package.whl").read_bytes()
    assert sdist.read_bytes() == (output / "package.tar.gz").read_bytes()
    assert not tuple(tmp_path.glob(".rc-*"))


def test_candidate_publication_cleans_staging_after_copy_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "package.whl").write_bytes(b"wheel")
    output = tmp_path / "candidate"
    artifacts = (ArtifactRecord("package.whl", "wheel", 5, "a" * 64),)

    def fail_copy(*_args: object, **_kwargs: object) -> None:
        raise OSError("injected copy failure")

    monkeypatch.setattr(release_module.shutil, "copyfile", fail_copy)
    with pytest.raises(ReleaseCandidateError, match="atomic publication"):
        _publish_candidate(output, source, artifacts, _safe_manifest())

    assert not output.exists()
    assert not tuple(tmp_path.glob(".rc-*"))
