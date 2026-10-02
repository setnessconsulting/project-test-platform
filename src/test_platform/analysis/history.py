"""Deterministic test history, flake, duration, and freshness analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from test_platform.adapters.results import TestCaseResultState
from test_platform.contracts import EvidenceFreshness, EvidenceState, ProfileBinding


@dataclass(frozen=True)
class HistoryObservation:
    """One observed test attempt with enough identity to judge equivalence and freshness."""

    test_id: str
    sha: str
    profile: ProfileBinding
    suite_id: str
    executor: str
    trust: str
    state: TestCaseResultState
    duration_seconds: float
    attempt: int
    observed_at: datetime


@dataclass(frozen=True)
class TestHistoryAssessment:
    """Deterministic history summary for one test."""

    test_id: str
    flaky: bool
    sample_count: int
    average_duration_seconds: float
    max_duration_seconds: float
    freshness: EvidenceFreshness


def _equivalence_key(item: HistoryObservation) -> tuple[object, ...]:
    return (
        item.sha,
        item.profile.profile_id,
        item.profile.version,
        item.suite_id,
        item.executor,
        item.trust,
    )


def _is_flaky(observations: tuple[HistoryObservation, ...]) -> bool:
    groups: dict[tuple[object, ...], set[TestCaseResultState]] = {}
    for item in observations:
        if item.state is TestCaseResultState.SKIPPED:
            continue
        groups.setdefault(_equivalence_key(item), set()).add(item.state)

    for states in groups.values():
        passed = TestCaseResultState.PASS in states
        failed = bool(states.intersection({TestCaseResultState.FAIL, TestCaseResultState.ERROR}))
        if passed and failed:
            return True
    return False


def _freshness(
    observations: tuple[HistoryObservation, ...],
    *,
    current_sha: str,
    current_profile: ProfileBinding,
    now: datetime,
    max_age_days: int | None = None,
) -> EvidenceFreshness:
    if not observations:
        return EvidenceFreshness(
            state=EvidenceState.NOT_EVALUABLE,
            reason="no result history is available",
        )

    current = tuple(
        item
        for item in observations
        if item.sha == current_sha and item.profile == current_profile
    )
    if current:
        states = {item.state for item in current}
        if TestCaseResultState.FAIL in states or TestCaseResultState.ERROR in states:
            return EvidenceFreshness(
                state=EvidenceState.MISSING,
                reason="current revision has failing or error evidence",
                qualified_sha=current_sha,
            )
        if max_age_days is not None:
            # An exact-revision result can still be too old to trust. The
            # profile declares this ceiling; enforce it here rather than
            # letting live evidence qualify forever.
            newest = max(item.observed_at for item in current)
            if (now - newest) > timedelta(days=max_age_days):
                return EvidenceFreshness(
                    state=EvidenceState.STALE,
                    reason=(
                        f"current-revision evidence is older than the declared "
                        f"{max_age_days}-day limit"
                    ),
                    qualified_sha=current_sha,
                )
        if TestCaseResultState.PASS in states:
            return EvidenceFreshness(
                state=EvidenceState.PROVEN,
                reason="current revision has passing evidence",
                qualified_sha=current_sha,
            )
        return EvidenceFreshness(
            state=EvidenceState.NOT_EVALUABLE,
            reason="current revision has only skipped evidence",
            qualified_sha=current_sha,
        )

    latest = max(observations, key=lambda item: item.observed_at)
    return EvidenceFreshness(
        state=EvidenceState.STALE,
        reason="available evidence is bound to another SHA or profile version",
        qualified_sha=latest.sha,
    )


def assess_test_history(
    test_id: str,
    observations: tuple[HistoryObservation, ...],
    *,
    current_sha: str,
    current_profile: ProfileBinding,
    now: datetime | None = None,
    max_age_days: int | None = None,
) -> TestHistoryAssessment:
    """Summarize exact test history without letting retries erase failures.

    ``max_age_days`` enforces the profile's declared evidence-age ceiling. It
    applies only when ``now`` is supplied, so an age ceiling is never enforced
    against a guessed clock.
    """
    relevant = tuple(
        sorted(
            (item for item in observations if item.test_id == test_id),
            key=lambda item: (
                item.observed_at,
                item.attempt,
                item.sha,
                item.executor,
                item.suite_id,
            ),
        )
    )

    durations = [item.duration_seconds for item in relevant]
    average = sum(durations) / len(durations) if durations else 0.0
    maximum = max(durations, default=0.0)

    return TestHistoryAssessment(
        test_id=test_id,
        flaky=_is_flaky(relevant),
        sample_count=len(relevant),
        average_duration_seconds=average,
        max_duration_seconds=maximum,
        freshness=_freshness(
            relevant,
            current_sha=current_sha,
            current_profile=current_profile,
            now=now or datetime.now(UTC),
            max_age_days=max_age_days,
        ),
    )
