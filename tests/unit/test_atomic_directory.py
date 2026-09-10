from __future__ import annotations

import errno
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from analog_validation_app import atomic_directory as atomic


def prepared(tmp_path: Path) -> Path:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "payload").write_bytes(b"complete result")
    return staging


def test_native_publication_and_existing_directory_are_preserved(
    tmp_path: Path,
) -> None:
    staging = prepared(tmp_path)
    target = tmp_path / "published"
    atomic.publish_directory_no_replace(staging, target)
    assert (target / "payload").read_bytes() == b"complete result"
    assert not staging.exists()
    staging = prepared(tmp_path)
    with pytest.raises(FileExistsError):
        atomic.publish_directory_no_replace(staging, target)
    assert (target / "payload").read_bytes() == b"complete result"
    assert staging.is_dir()


@pytest.mark.parametrize(
    "kind", ["same", "different-parent", "file", "missing", "empty-target"]
)
def test_invalid_publication_never_moves_the_input(tmp_path: Path, kind: str) -> None:
    staging = prepared(tmp_path)
    target = tmp_path / "published"
    if kind == "same":
        target = staging
    elif kind == "different-parent":
        target = tmp_path / "other" / "published"
    elif kind == "file":
        staging = staging / "payload"
    elif kind == "missing":
        staging = tmp_path / "absent"
    else:
        target.mkdir()
    with pytest.raises(OSError):
        atomic.publish_directory_no_replace(staging, target)
    assert (tmp_path / "staging" / "payload").read_bytes() == b"complete result"
    if kind == "empty-target":
        assert tuple(target.iterdir()) == ()


def test_windows_rename_race_does_not_replace_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging = prepared(tmp_path)
    target = tmp_path / "published"
    monkeypatch.setattr(atomic.sys, "platform", "win32")

    def concurrent_target(source: Path, destination: Path) -> None:
        destination.mkdir()
        raise FileExistsError(errno.EEXIST, "concurrent writer")

    monkeypatch.setattr(atomic.os, "rename", concurrent_target)
    with pytest.raises(FileExistsError):
        atomic.publish_directory_no_replace(staging, target)
    assert staging.is_dir()
    assert tuple(target.iterdir()) == ()


def test_windows_successful_publication_uses_native_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging = prepared(tmp_path)
    target = tmp_path / "published"
    native_rename = atomic.os.rename
    calls: list[tuple[Path, Path]] = []

    def rename(source: Path, destination: Path) -> None:
        calls.append((source, destination))
        native_rename(source, destination)

    monkeypatch.setattr(atomic.sys, "platform", "win32")
    monkeypatch.setattr(atomic.os, "rename", rename)
    atomic.publish_directory_no_replace(staging, target)
    assert calls == [(staging, target)]
    assert (target / "payload").read_bytes() == b"complete result"
    assert not staging.exists()


@pytest.mark.parametrize("code", [0, errno.EEXIST, errno.ENOTSUP])
def test_linux_requires_native_noreplace_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    staging = prepared(tmp_path)
    target = tmp_path / "published"
    calls: list[tuple[Any, ...]] = []

    def rename(*args: Any) -> int:
        calls.append(args)
        return -1 if code else 0

    monkeypatch.setattr(atomic.sys, "platform", "linux")
    monkeypatch.setattr(
        atomic.ctypes, "CDLL", lambda *a, **kw: SimpleNamespace(renameat2=rename)
    )
    monkeypatch.setattr(atomic.ctypes, "get_errno", lambda: code)
    if code:
        with pytest.raises(OSError) as result:
            atomic.publish_directory_no_replace(staging, target)
        assert result.value.errno == code
    else:
        atomic.publish_directory_no_replace(staging, target)
    assert calls == [
        (-100, atomic.os.fsencode(staging), -100, atomic.os.fsencode(target), 1)
    ]


@pytest.mark.parametrize("platform", ["linux", "unsupported"])
def test_unsupported_native_operation_keeps_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    staging = prepared(tmp_path)
    target = tmp_path / "published"
    monkeypatch.setattr(atomic.sys, "platform", platform)
    monkeypatch.setattr(atomic.ctypes, "CDLL", lambda *a, **kw: object())
    with pytest.raises(OSError) as result:
        atomic.publish_directory_no_replace(staging, target)
    assert result.value.errno == errno.ENOTSUP
    assert (staging / "payload").read_bytes() == b"complete result"
    assert not target.exists()
