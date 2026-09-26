from __future__ import annotations

import json
from typing import Any

from test_platform.cli import main


def test_doctor_json_is_machine_readable(capsys: Any) -> None:
    exit_code = main(["doctor", "--json"])

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["overall"] == "PASS"
    assert payload["checks"][0]["name"] == "python"
