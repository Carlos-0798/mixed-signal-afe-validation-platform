"""Release-candidate determinism, privacy, and create-new safety tests."""

from __future__ import annotations

import gzip
import io
import tarfile
from pathlib import Path

import pytest

from tools.release_candidate_check import (
    RELEASE_CANDIDATE_SCHEMA_VERSION,
    ArtifactRecord,
    ReleaseCandidateError,
    _compare_builds,
    _manifest,
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
