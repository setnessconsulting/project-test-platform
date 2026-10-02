from __future__ import annotations

from test_platform.analysis import BehaviorEvidenceObservation, analyze_behavior_gaps
from test_platform.contracts import (
    Behavior,
    BehaviorDocument,
    Criticality,
    CriticalJourney,
    EvidenceClass,
    EvidenceState,
    ProfileBinding,
)

PROFILE = ProfileBinding(profile_id="web-application-v1", version="1.0.0")
SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _document() -> BehaviorDocument:
    return BehaviorDocument(
        behaviors=(
            Behavior(
                behavior_id="auth.sign-in",
                description="Authorized user can sign in.",
                criticality=Criticality.CRITICAL,
                required_evidence=(EvidenceClass.INTEGRATION, EvidenceClass.E2E),
            ),
        ),
        critical_journeys=(
            CriticalJourney(
                journey_id="login",
                description="User completes login.",
                behavior_ids=("auth.sign-in",),
            ),
        ),
    )


def test_current_exact_evidence_proves_behavior_and_journey() -> None:
    observations = (
        BehaviorEvidenceObservation(
            evidence_id="integration-1",
            subject_id="auth.sign-in",
            evidence_class=EvidenceClass.INTEGRATION,
            state=EvidenceState.PROVEN,
            sha=SHA,
            profile=PROFILE,
        ),
        BehaviorEvidenceObservation(
            evidence_id="e2e-1",
            subject_id="auth.sign-in",
            evidence_class=EvidenceClass.E2E,
            state=EvidenceState.PROVEN,
            sha=SHA,
            profile=PROFILE,
        ),
        BehaviorEvidenceObservation(
            evidence_id="journey-e2e-1",
            subject_id="journey:login",
            evidence_class=EvidenceClass.E2E,
            state=EvidenceState.PROVEN,
            sha=SHA,
            profile=PROFILE,
        ),
    )

    findings = analyze_behavior_gaps(_document(), observations, sha=SHA, profile=PROFILE)

    assert {item.behavior_id: item.state for item in findings} == {
        "auth.sign-in": EvidenceState.PROVEN,
        "journey:login": EvidenceState.PROVEN,
    }


def test_old_sha_is_stale_not_proven() -> None:
    observations = (
        BehaviorEvidenceObservation(
            evidence_id="old-e2e",
            subject_id="auth.sign-in",
            evidence_class=EvidenceClass.E2E,
            state=EvidenceState.PROVEN,
            sha="oldsha1234567",
            profile=PROFILE,
        ),
    )

    findings = analyze_behavior_gaps(_document(), observations, sha=SHA, profile=PROFILE)
    behavior = next(item for item in findings if item.behavior_id == "auth.sign-in")

    assert behavior.state is EvidenceState.MISSING
    assert "missing required integration" in " ".join(behavior.reasons)
    assert "stale" in " ".join(behavior.reasons)


def test_incomplete_evidence_is_not_evaluable_instead_of_pass() -> None:
    observations = (
        BehaviorEvidenceObservation(
            evidence_id="integration-blocked",
            subject_id="auth.sign-in",
            evidence_class=EvidenceClass.INTEGRATION,
            state=EvidenceState.NOT_EVALUABLE,
            sha=SHA,
            profile=PROFILE,
        ),
        BehaviorEvidenceObservation(
            evidence_id="e2e-1",
            subject_id="auth.sign-in",
            evidence_class=EvidenceClass.E2E,
            state=EvidenceState.PROVEN,
            sha=SHA,
            profile=PROFILE,
        ),
    )

    findings = analyze_behavior_gaps(_document(), observations, sha=SHA, profile=PROFILE)
    behavior = next(item for item in findings if item.behavior_id == "auth.sign-in")

    assert behavior.state is EvidenceState.NOT_EVALUABLE


def test_journey_cannot_pass_when_constituent_behavior_is_missing() -> None:
    observations = (
        BehaviorEvidenceObservation(
            evidence_id="journey-e2e-1",
            subject_id="journey:login",
            evidence_class=EvidenceClass.E2E,
            state=EvidenceState.PROVEN,
            sha=SHA,
            profile=PROFILE,
        ),
    )

    findings = analyze_behavior_gaps(_document(), observations, sha=SHA, profile=PROFILE)
    journey = next(item for item in findings if item.behavior_id == "journey:login")

    assert journey.state is EvidenceState.MISSING
