from __future__ import annotations

from pathlib import Path

from test_platform.public_safety import scan


def test_scanner_rejects_high_confidence_secret(tmp_path: Path) -> None:
    token = "gh" + "p_" + ("a" * 24)
    (tmp_path / "bad.txt").write_text(token, encoding="utf-8")

    findings = scan(tmp_path)

    assert len(findings) == 1
    assert findings[0].rule == "github-token"


def test_scanner_rejects_private_windows_user_path(tmp_path: Path) -> None:
    private_path = "C:" + "\\" + "Users" + "\\" + "Alice" + "\\" + "repo"
    (tmp_path / "bad.txt").write_text(private_path, encoding="utf-8")

    findings = scan(tmp_path)

    assert len(findings) == 1
    assert findings[0].rule == "windows-user-path"


def test_scanner_allows_documented_placeholder_path(tmp_path: Path) -> None:
    placeholder = "C:" + "\\" + "Users" + "\\" + "username" + "\\" + "repo"
    (tmp_path / "ok.txt").write_text(placeholder, encoding="utf-8")

    assert scan(tmp_path) == ()
