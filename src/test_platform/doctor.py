"""Bounded, credential-free environment diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import platform
import sys
from typing import Any

from test_platform import __version__

MINIMUM_PYTHON = (3, 12)


@dataclass(frozen=True)
class DoctorCheck:
    """One deterministic doctor check."""

    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class DoctorReport:
    """Credential-free diagnostics safe for public output."""

    version: str
    overall: str
    checks: tuple[DoctorCheck, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "version": self.version,
            "overall": self.overall,
            "checks": [asdict(check) for check in self.checks],
        }


def run_doctor() -> DoctorReport:
    """Run bounded checks that do not inspect credentials or private portfolio state."""
    python_ok = sys.version_info >= MINIMUM_PYTHON
    checks = (
        DoctorCheck(
            name="python",
            status="PASS" if python_ok else "FAIL",
            detail=(
                f"Python {platform.python_version()} "
                f"(requires >= {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]})"
            ),
        ),
        DoctorCheck(
            name="public-core",
            status="PASS",
            detail="Doctor is credential-free and does not inspect private portfolio data.",
        ),
    )
    overall = "PASS" if all(check.status == "PASS" for check in checks) else "FAIL"
    return DoctorReport(version=__version__, overall=overall, checks=checks)
