from __future__ import annotations

from datetime import UTC, datetime, timedelta

from test_platform.adapters.results import TestCaseResultState
from test_platform.analysis import HistoryObservation, assess_test_history
from test_platform.contracts import EvidenceState, ProfileBinding

PROFILE = ProfileBinding(profile_id="python-control-plane-v1", version="1.0.0")
SHA = "abcdef1234567"
NOW = datetime(2026, 9, 25, tzinfo=UTC)


def _sample(
    state: TestCaseResultState,
    *,
    sha: str = SHA,
    profile: ProfileBinding = PROFILE,
    attempt: int = 1,
    seconds: float = 1.0,
    observed_at: datetime = NOW,
) -> HistoryObservation:
    return HistoryObservation(
        test_id="pytest:tests/test_policy.py",
        sha=sha,
        profile=profile,
        suite_id="standard",
        executor="jenkins",
        trust="pr-untrusted",
        state=state,
        duration_seconds=seconds,
        attempt=attempt,
        observed_at=observed_at,
    )


def test_retry_pass_does_not_erase_flake() -> None:
    assessment = assess_test_history(
        "pytest:tests/test_policy.py",
        (
            _sample(TestCaseResultState.FAIL, attempt=1),
            _sample(TestCaseResultState.PASS, attempt=2),
        ),
        current_sha=SHA,
        current_profile=PROFILE,
    )

    assert assessment.flaky is True
    assert assessment.freshness.state is EvidenceState.MISSING


def test_current_pass_is_proven_when_no_failure_exists() -> None:
    assessment = assess_test_history(
        "pytest:tests/test_policy.py",
        (_sample(TestCaseResultState.PASS, seconds=2.0),),
        current_sha=SHA,
        current_profile=PROFILE,
    )

    assert assessment.flaky is False
    assert assessment.freshness.state is EvidenceState.PROVEN
    assert assessment.average_duration_seconds == 2.0


def test_old_sha_or_profile_is_stale() -> None:
    assessment = assess_test_history(
        "pytest:tests/test_policy.py",
        (
            _sample(
                TestCaseResultState.PASS,
                sha="oldsha1234567",
                observed_at=NOW - timedelta(days=1),
            ),
        ),
        current_sha=SHA,
        current_profile=PROFILE,
    )

    assert assessment.freshness.state is EvidenceState.STALE
    assert assessment.freshness.qualified_sha == "oldsha1234567"


def test_only_skipped_current_evidence_is_not_evaluable() -> None:
    assessment = assess_test_history(
        "pytest:tests/test_policy.py",
        (_sample(TestCaseResultState.SKIPPED),),
        current_sha=SHA,
        current_profile=PROFILE,
    )

    assert assessment.freshness.state is EvidenceState.NOT_EVALUABLE


def test_no_history_is_not_evaluable() -> None:
    assessment = assess_test_history(
        "pytest:tests/test_policy.py",
        (),
        current_sha=SHA,
        current_profile=PROFILE,
    )

    assert assessment.sample_count == 0
    assert assessment.freshness.state is EvidenceState.NOT_EVALUABLE
