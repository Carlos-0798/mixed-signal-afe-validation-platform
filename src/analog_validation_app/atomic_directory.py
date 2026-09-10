"""Atomic create-new directory publication on the Windows/Linux product targets."""

from __future__ import annotations

import ctypes
import errno
import os
import sys
from pathlib import Path


def publish_directory_no_replace(staging: Path, destination: Path) -> None:
    """Move a prepared sibling directory without replacing even an empty target.

    A plain POSIX rename can replace a concurrently created empty directory.
    Linux therefore requires RENAME_NOREPLACE; unsupported platforms/filesystems
    fail closed rather than falling back to a check-then-rename race.
    """
    source = staging.absolute()
    target = destination.absolute()
    if source.parent != target.parent or source == target:
        raise OSError(errno.EINVAL, "Publication requires distinct sibling directories")
    if source.is_symlink() or not source.is_dir():
        raise OSError(errno.EINVAL, "Publication source must be a prepared directory")
    if target.exists() or target.is_symlink():
        raise FileExistsError(errno.EEXIST, "Output already exists", str(target))
    if sys.platform == "win32":
        os.rename(source, target)
        return
    if sys.platform != "linux":
        raise OSError(
            errno.ENOTSUP, "Atomic create-new publication requires Windows or Linux"
        )
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, "renameat2", None)
    if rename is None:
        raise OSError(errno.ENOTSUP, "This runtime does not provide renameat2")
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    # Absolute paths ignore dirfd. Linux RENAME_NOREPLACE is the low bit (1).
    result = rename(-100, os.fsencode(source), -100, os.fsencode(target), 1)
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(target))
