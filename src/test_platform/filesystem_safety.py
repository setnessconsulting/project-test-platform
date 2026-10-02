"""Shared filesystem traversal guards for untrusted repository trees.

Every component that walks a caller-supplied repository root (discovery, the
public-safety scanner, manifest loading) must share these helpers so that one
hardening change cannot be bypassed by using a different entry point.

Two classes of indirection are rejected together:

* POSIX/Windows symlinks, which ``Path.is_symlink()`` detects; and
* Windows junctions and other reparse points, which ``Path.is_symlink()``
  returns ``False`` for even though directory traversal follows them.

An explicit depth bound is always supplied by the caller. Bounding depth rather
than relying on a caught ``RecursionError`` or on ``os.walk`` internals is what
makes the walk total: a symlink or junction loop terminates because the path
itself is rejected, not because a limit happened to be hit.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["is_indirect", "bounded_walk"]


def is_indirect(path: Path) -> bool:
    """Return True when the path is a symlink, junction, or reparse point.

    ``Path.is_symlink`` alone is not sufficient on Windows: junctions report
    ``is_symlink() is False`` yet are traversed by ``os.walk`` and by
    ``Path.resolve``. Python 3.12 provides ``os.path.isjunction``; the
    ``st_file_attributes`` check is the portable fallback for the remaining
    reparse-point forms on older or non-Windows platforms.
    """
    try:
        if path.is_symlink():
            return True
    except FileNotFoundError:
        # A path that does not exist is neither a link nor a junction. The
        # lstat check below treats a missing component as indeterminate, which
        # would wrongly flag every not-yet-created manifest subdirectory.
        return False
    except OSError:
        return True

    is_junction = getattr(os.path, "isjunction", None)
    if is_junction is not None:
        try:
            if is_junction(path):
                return True
        except FileNotFoundError:
            return False
        except (OSError, ValueError):
            return True

    try:
        stat = path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    # FILE_ATTRIBUTE_REPARSE_POINT. Only meaningful on Windows, where lstat
    # exposes st_file_attributes; absent elsewhere.
    attributes = getattr(stat, "st_file_attributes", 0)
    return bool(attributes & 0x400)


def bounded_walk(
    root: Path,
    *,
    max_depth: int,
    max_directories: int,
    max_entries: int,
) -> tuple[tuple[tuple[Path, tuple[Path, ...]], ...], bool]:
    """Walk ``root`` without following links, bounded in depth and breadth.

    Returns ``(directories, limit_exceeded)`` where ``directories`` is a tuple
    of ``(directory, file_paths)`` pairs in deterministic sorted order and
    ``limit_exceeded`` reports whether any bound was reached. The walk stops at
    the first bound it exceeds rather than continuing partially, so a caller can
    treat an over-limit repository as indeterminate instead of silently
    scanning an arbitrary prefix.
    """
    visited_directories = 0
    seen_entries = 0
    limit_exceeded = False
    results: list[tuple[Path, tuple[Path, ...]]] = []

    for current, dirs, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)

        visited_directories += 1
        seen_entries += len(dirs) + len(filenames)
        if visited_directories > max_directories or seen_entries > max_entries:
            limit_exceeded = True
            break

        try:
            relative = current_path.relative_to(root)
        except ValueError:
            # Walked outside the requested root; treat as indeterminate.
            limit_exceeded = True
            break

        depth = len(relative.parts)
        if depth >= max_depth:
            limit_exceeded = True
            dirs[:] = []
            continue

        safe_dirs: list[str] = []
        for name in sorted(dirs):
            candidate = current_path / name
            if is_indirect(candidate):
                # A link or junction here could escape the root or form a loop.
                continue
            safe_dirs.append(name)
        dirs[:] = safe_dirs

        safe_files = [
            path
            for path in sorted(current_path / name for name in filenames)
            if not is_indirect(path)
        ]
        results.append((current_path, tuple(safe_files)))

    return tuple(results), limit_exceeded