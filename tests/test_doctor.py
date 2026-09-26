from __future__ import annotations

from test_platform.doctor import run_doctor


def test_doctor_is_credential_free_and_passes_supported_python() -> None:
    report = run_doctor()

    assert report.overall == "PASS"
    assert [check.name for check in report.checks] == ["python", "public-core"]
    assert all(check.status == "PASS" for check in report.checks)
