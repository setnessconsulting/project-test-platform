from __future__ import annotations

import pytest

from test_platform.analysis.mutation import (
    MutationAnalysisError,
    MutationLimits,
    MutationTrial,
    MutationTrialState,
    analyze_mutation_evidence,
)
from test_platform.contracts import (
    EvidenceState,
    ExecutionTarget,
    ExecutionTrustClass,
    QualityProfile,
    RequirementLevel,
)


def _profile(level: RequirementLevel) -> QualityProfile:
    return QualityProfile(
        profile_id="python-control-plane-v1",
        version="1.0.0",
        requirements=(),
        allowed_trust=(ExecutionTrustClass.PR_UNTRUSTED,),
        recommended_execution=(ExecutionTarget.JENKINS,),
        mutation_analysis=level,
    )


def test_required_mutation_analysis_needs_trials() -> None:
    finding = analyze_mutation_evidence(_profile(RequirementLevel.REQUIRED), ())
    assert finding.state is EvidenceState.MISSING


def test_surviving_mutation_is_an_evidence_gap_not_an_auto_test_request() -> None:
    finding = analyze_mutation_evidence(
        _profile(RequirementLevel.REQUIRED),
        (
            MutationTrial(
                trial_id="mut-1",
                target_id="policy.rule",
                state=MutationTrialState.SURVIVED,
                duration_seconds=0.5,
                evidence_id="mutation-run-1",
            ),
        ),
    )

    assert finding.state is EvidenceState.MISSING
    assert "mut-1" in " ".join(finding.reasons)


def test_timeout_makes_mutation_evidence_not_evaluable() -> None:
    finding = analyze_mutation_evidence(
        _profile(RequirementLevel.REQUIRED),
        (
            MutationTrial(
                trial_id="mut-1",
                target_id="policy.rule",
                state=MutationTrialState.TIMEOUT,
                duration_seconds=2.0,
            ),
        ),
    )

    assert finding.state is EvidenceState.NOT_EVALUABLE


def test_not_applicable_profile_does_not_become_a_gate() -> None:
    finding = analyze_mutation_evidence(
        _profile(RequirementLevel.NOT_APPLICABLE),
        (),
    )
    assert finding.state is EvidenceState.NOT_APPLICABLE


def test_mutation_cost_bounds_fail_closed() -> None:
    trial = MutationTrial(
        trial_id="mut-1",
        target_id="policy.rule",
        state=MutationTrialState.KILLED,
        duration_seconds=11.0,
    )
    with pytest.raises(MutationAnalysisError, match="duration"):
        analyze_mutation_evidence(
            _profile(RequirementLevel.REQUIRED),
            (trial,),
            limits=MutationLimits(max_trials=10, max_total_seconds=10.0),
        )
