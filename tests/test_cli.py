from __future__ import annotations

import json
from typing import Any

import pytest

from test_platform.cli import build_parser, main


def test_doctor_json_uses_versioned_machine_envelope(capsys: Any) -> None:
    exit_code = main(["doctor", "--json"])

    assert exit_code == 0
    captured = capsys.readouterr()
    envelope = json.loads(captured.out)
    assert envelope["schema_version"] == "1"
    assert envelope["command"] == "doctor"
    assert envelope["payload"]["overall"] == "PASS"
    assert envelope["payload"]["checks"][0]["name"] == "python"


def test_validate_browser_game_fixture_is_offline_and_machine_readable(
    capsys: Any,
) -> None:
    exit_code = main(
        [
            "validate",
            "--repo",
            "examples/browser-game",
            "--json",
        ]
    )

    assert exit_code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["payload"]["validation"] == "pass"
    assert envelope["payload"]["profile"]["profile_id"] == "browser-game-v1"
    assert envelope["payload"]["manifest"]["schema_version"] == "1"


@pytest.mark.parametrize(
    "command",
    [
        "validate",
        "inventory",
        "behaviors",
        "audit",
        "gaps",
        "plan",
        "evaluate",
        "actions",
        "migration-plan",
        "report",
        "portfolio-export",
        "doctor",
        "guide",
    ],
)
def test_stable_command_names_have_help(command: str) -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args([command, "--help"])
    assert exc.value.code == 0


def test_invalid_repository_input_returns_meaningful_nonzero(
    tmp_path: Any,
    capsys: Any,
) -> None:
    exit_code = main(
        [
            "validate",
            "--repo",
            str(tmp_path),
            "--json",
        ]
    )

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "manifest" in captured.err.lower()
