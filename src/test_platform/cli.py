"""Command-line interface for the Test Platform."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from test_platform import __version__
from test_platform.doctor import run_doctor


def build_parser() -> argparse.ArgumentParser:
    """Build the stable top-level parser."""
    parser = argparse.ArgumentParser(
        prog="test-platform",
        description="Behavioral verification and quality-evidence platform.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor = subparsers.add_parser(
        "doctor",
        help="Run bounded credential-free environment diagnostics.",
    )
    doctor.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        report = run_doctor()
        if args.json:
            print(json.dumps(report.as_dict(), sort_keys=True, separators=(",", ":")))
        else:
            print(f"Test Platform {report.version}: {report.overall}")
            for check in report.checks:
                print(f"- {check.name}: {check.status} — {check.detail}")
        return 0 if report.overall == "PASS" else 1

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
