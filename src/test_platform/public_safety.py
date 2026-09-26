"""Credential-free public-repository safety scanner.

The scanner is intentionally conservative and deterministic. It detects a small set of
high-confidence secret/path shapes without attempting to replace a dedicated enterprise
secret scanner.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
import re

IGNORED_PARTS = {
    ".git",
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

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key", re.compile(re.escape("-----BEGIN " + "PRIVATE KEY-----"))),
)

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


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        try:
            if path.stat().st_size > MAX_TEXT_BYTES:
                continue
        except OSError:
            continue
        yield path


def scan(root: Path) -> tuple[SafetyFinding, ...]:
    """Scan public text files for high-confidence secret and private-path shapes."""
    findings: list[SafetyFinding] = []
    for path in _iter_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(root).as_posix()
        for line_number, line in enumerate(text.splitlines(), start=1):
            for rule, pattern in (*SECRET_PATTERNS, *PRIVATE_PATH_PATTERNS):
                if pattern.search(line):
                    findings.append(SafetyFinding(path=relative, rule=rule, line=line_number))
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
