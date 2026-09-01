"""Bounded local UTF-8 file access shared by result export formats."""

from __future__ import annotations

import os
import tempfile
from os import PathLike
from pathlib import Path

from .errors import (
    ResultExportExistsError,
    ResultExportLimitError,
    ResultExportPathError,
)


def _path(value: str | PathLike[str]) -> Path:
    if not isinstance(value, (str, PathLike)):
        raise ResultExportPathError("path must be a string or path-like value")
    try:
        path = Path(value)
    except (TypeError, ValueError, OSError) as error:
        raise ResultExportPathError("path is invalid") from error
    if not path.name:
        raise ResultExportPathError("path must identify a file")
    return path


def read_bounded_utf8(
    value: str | PathLike[str],
    *,
    maximum_bytes: int,
) -> str:
    """Read one regular local file with a pre/post-read byte limit."""

    path = _path(value)
    try:
        if not path.exists():
            raise ResultExportPathError("result file does not exist")
        if not path.is_file():
            raise ResultExportPathError("result path must identify a regular file")
        if path.stat().st_size > maximum_bytes:
            raise ResultExportLimitError("result file exceeds the byte limit")
        content = path.read_bytes()
    except (ResultExportPathError, ResultExportLimitError):
        raise
    except OSError as error:
        raise ResultExportPathError("result file could not be read") from error
    if len(content) > maximum_bytes:
        raise ResultExportLimitError("result file exceeds the byte limit")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ResultExportPathError("result file must contain UTF-8 text") from error


def write_utf8_atomic(
    value: str | PathLike[str],
    text: str,
    *,
    overwrite: bool,
) -> Path:
    """Atomically publish text and deny replacing an existing path by default."""

    path = _path(value)
    if not isinstance(text, str):
        raise ResultExportPathError("text must be a string")
    if not isinstance(overwrite, bool):
        raise ResultExportPathError("overwrite must be a bool")
    parent = path.parent
    try:
        if not parent.exists() or not parent.is_dir():
            raise ResultExportPathError("destination parent directory must exist")
        if path.exists() and not overwrite:
            raise ResultExportExistsError("destination already exists")
    except (ResultExportPathError, ResultExportExistsError):
        raise
    except OSError as error:
        raise ResultExportPathError("destination cannot be prepared") from error

    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=parent,
            delete=False,
        ) as temporary_handle:
            temporary = Path(temporary_handle.name)
            temporary_handle.write(text.encode("utf-8"))
            temporary_handle.flush()
            os.fsync(temporary_handle.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError as error:
                raise ResultExportExistsError("destination already exists") from error
            temporary.unlink()
    except ResultExportExistsError:
        raise
    except (OSError, UnicodeEncodeError) as error:
        raise ResultExportPathError("result file could not be written") from error
    finally:
        try:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        except OSError:
            pass
    return path


__all__: list[str] = []
