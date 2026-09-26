from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from test_platform.analysis.evaluator import (
    QualityEvaluationError,
    evaluate_quality,
    exact_waiver_scope,
)
from test_platform.contracts import (
    EvidenceClass,
    EvidenceState,
    ExecutionTarget,
    ExecutionTrustClass,
    ProfileBinding,
    ProfileRequirement,
    QualityProfile,
    QualityResult,
    RequirementLevel,
    Waiver,
)

NOW = datetime(2026, 9, 25, tzinfo=UTC)
REPO = "setnessconsulting/example"


def _profile(*, non_waivable: bool = False, version: str = "1.0.0") -> QualityProfile:
    return QualityProfile(
        profile_id="python-control-plane-v1",
        version=version,
        requirements=(
            ProfileRequirement(
                rule_id="security-negative-path",
                evidence_class=EvidenceClass.ADVERSARIAL,
                level=RequirementLevel.REQUIRED,
                non_waivable=non_waivable,
                description="Security boundary must have negative-path evidence.",
            ),
        ),
        allowed_trust=(ExecutionTrustClass.PR_UNTRUSTED,),
        recommended_execution=(ExecutionTarget.JENKINS,),
    )


def _waiver(profile: QualityProfile, *, expires: datetime | None = None) -> Waiver:
    binding = ProfileBinding(profile_id=profile.profile_id, version=profile.version)
    return Waiver(
        waiver_id="waiver-1",
        rule_id="security-negative-path",
        scope=exact_waiver_scope(REPO, binding),
        reason="temporary reviewed compatibility gap",
        owner_decision_ref="API-999",
        created_at=NOW - timedelta(days=1),
        expires_at=expires,
    )


def test_proven_required_rule_passes_without_score() -> None:
    result = evaluate_quality(
        repository=REPO,
        sha="abcdef1234567",
        profile=_profile(),
        rule_states={"security-negative-path": EvidenceState.PROVEN},
        now=NOW,
    )

    assert result.result is QualityResult.PASS
    assert result.waiver_ids == ()


def test_missing_waivable_rule_can_use_exact_current_profile_waiver() -> None:
    profile = _profile()
    result = evaluate_quality(
        repository=REPO,
        sha="abcdef1234567",
        profile=profile,
        rule_states={"security-negative-path": EvidenceState.MISSING},
        waivers=(_waiver(profile),),
        now=NOW,
    )

    assert result.result is QualityResult.PASS
    assert result.waiver_ids == ("waiver-1",)


def test_expired_or_old_profile_waiver_does_not_apply() -> None:
    profile = _profile(version="2.0.0")
    old_profile = _profile(version="1.0.0")
    result = evaluate_quality(
        repository=REPO,
        sha="abcdef1234567",
        profile=profile,
        rule_states={"security-negative-path": EvidenceState.MISSING},
        waivers=(
            _waiver(old_profile),
            _waiver(profile, expires=NOW - timedelta(seconds=1)),
        ),
        now=NOW,
    )

    assert result.result is QualityResult.FAIL
    assert result.waiver_ids == ()


def test_not_evaluable_evidence_cannot_be_waived_into_pass() -> None:
    profile = _profile()
    result = evaluate_quality(
        repository=REPO,
        sha="abcdef1234567",
        profile=profile,
        rule_states={"security-negative-path": EvidenceState.NOT_EVALUABLE},
        waivers=(_waiver(profile),),
        now=NOW,
    )

    assert result.result is QualityResult.NOT_EVALUABLE
    assert result.waiver_ids == ()


def test_non_waivable_rule_ignores_otherwise_valid_waiver() -> None:
    profile = _profile(non_waivable=True)
    result = evaluate_quality(
        repository=REPO,
        sha="abcdef1234567",
        profile=profile,
        rule_states={"security-negative-path": EvidenceState.MISSING},
        waivers=(_waiver(profile),),
        now=NOW,
    )

    assert result.result is QualityResult.FAIL


def test_wildcard_waiver_scope_fails_closed() -> None:
    profile = _profile()
    waiver = Waiver(
        waiver_id="wild",
        rule_id="security-negative-path",
        scope="repo:*",
        reason="too broad",
        owner_decision_ref="API-999",
        created_at=NOW - timedelta(days=1),
    )

    with pytest.raises(QualityEvaluationError, match="wildcard"):
        evaluate_quality(
            repository=REPO,
            sha="abcdef1234567",
            profile=profile,
            rule_states={"security-negative-path": EvidenceState.MISSING},
            waivers=(waiver,),
            now=NOW,
        )


def test_explicit_blocker_outranks_other_pass_evidence() -> None:
    result = evaluate_quality(
        repository=REPO,
        sha="abcdef1234567",
        profile=_profile(),
        rule_states={"security-negative-path": EvidenceState.PROVEN},
        blocked_reasons=("qualified executor unavailable",),
        now=NOW,
    )

    assert result.result is QualityResult.BLOCKED
