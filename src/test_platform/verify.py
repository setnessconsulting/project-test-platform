"""Canonical clean-checkout verification entry point."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence


def _run(command: Sequence[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def main() -> int:
    """Run deterministic repository verification."""
    python = sys.executable
    commands: tuple[tuple[str, ...], ...] = (
        (python, "-m", "compileall", "-q", "src", "tests"),
        (python, "-m", "test_platform.public_safety", "."),
        (python, "-m", "test_platform.schema_registry", "--check"),
        (python, "-m", "ruff", "check", "."),
        (python, "-m", "mypy", "src/test_platform"),
        (python, "-m", "pytest"),
        (python, "-m", "build"),
    )
    for command in commands:
        _run(command)
    print("verify: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
