"""Credential-free public-repository safety scanner.

The scanner is intentionally conservative and deterministic. It detects a small set of
high-confidence secret/path shapes without attempting to replace a dedicated enterprise
secret scanner.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from test_platform.filesystem_safety import bounded_walk
from test_platform.secret_shapes import SECRET_PATTERNS

__all__ = [
    "IGNORED_PARTS",
    "MAX_DEPTH",
    "MAX_DIRECTORIES",
    "MAX_FILES",
    "MAX_TEXT_BYTES",
    "PRIVATE_PATH_PATTERNS",
    "SECRET_PATTERNS",
    "SafetyFinding",
    "scan",
]

IGNORED_PARTS = {
    ".git",
    ".hypothesis",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    "artifacts",
    ".private",
}

MAX_TEXT_BYTES = 2_000_000
MAX_FILES = 20_000
MAX_DIRECTORIES = 20_000
MAX_DEPTH = 12

PRIVATE_PATH_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "windows-user-path",
        re.compile(r"(?i)\b[A-Z]:\\Users\\(?!example\\|user\\|username\\)[^\\\s]+\\"),
    ),
    (
        "unix-user-path",
        re.compile(r"/(?:home|Users)/(?!example/|user/|username/)[^/\s]+/"),
    ),
)


@dataclass(frozen=True)
class SafetyFinding:
    """One public-safety finding."""

    path: str
    rule: str
    line: int


def _iter_files(root: Path) -> tuple[tuple[Path, ...], bool]:
    """Return bounded, non-following candidate files plus a limit-exceeded flag.

    ``Path.rglob`` follows links and has no breadth or depth bound, so a
    symlink or junction loop inside an untrusted repository would make the
    release guard unbounded. The walk is bounded instead, and an over-limit
    repository is reported rather than partially scanned.
    """
    directories, limit_exceeded = bounded_walk(
        root,
        max_depth=MAX_DEPTH,
        max_directories=MAX_DIRECTORIES,
        max_entries=MAX_FILES * 2,
    )
    candidates = tuple(
        path
        for _directory, files in directories
        for path in files
        if not any(part in IGNORED_PARTS for part in path.parts)
    )
    return candidates, limit_exceeded


def _relative_to_root(path: Path, root: Path) -> str:
    """Return a repository-relative path without leaking a host path."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def scan(root: Path) -> tuple[SafetyFinding, ...]:
    """Scan public text files for high-confidence secret and private-path shapes.

    An unreadable or oversized file, or a repository that exceeds the scan
    bounds, produces a finding rather than being skipped: a file the guard
    cannot read is not evidence that the repository is clean.
    """
    findings: list[SafetyFinding] = []
    emitted: set[tuple[str, str]] = set()

    def add(path: str, rule: str, line: int) -> None:
        if (path, rule) in emitted:
            return
        emitted.add((path, rule))
        findings.append(SafetyFinding(path=path, rule=rule, line=line))

    candidates, limit_exceeded = _iter_files(root)

    for path in candidates:
        relative = _relative_to_root(path, root)
        try:
            size = path.stat().st_size
        except OSError:
            add(relative, "unreadable-file", 1)
            continue
        if size > MAX_TEXT_BYTES:
            add(relative, "oversize-file-not-scanned", 1)
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            for rule, pattern in (*SECRET_PATTERNS, *PRIVATE_PATH_PATTERNS):
                if pattern.search(line):
                    add(relative, rule, line_number)

    if limit_exceeded:
        add(".", "scan-limit-exceeded-not-fully-scanned", 1)
    return tuple(findings)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the public-safety scanner."""
    parser = argparse.ArgumentParser(description="Scan the public core for unsafe content.")
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)

    findings = scan(Path(args.root).resolve())
    if findings:
        for finding in findings:
            print(f"{finding.path}:{finding.line}: {finding.rule}")
        return 1
    print("public-safety: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
