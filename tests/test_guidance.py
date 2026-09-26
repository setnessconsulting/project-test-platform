from __future__ import annotations

import pytest

from test_platform.contracts import (
    Behavior,
    BehaviorDocument,
    CriticalJourney,
    Criticality,
    EvidenceClass,
    EvidenceState,
    ExecutionTarget,
    ExecutionTrustClass,
    GapFinding,
    ProfileBinding,
    QualityProfile,
    RepositoryManifest,
    SuiteDefinition,
    TestCaseObservation,
    TestInventory,
)
from test_platform.guidance import GuidanceError, generate_agent_guidance


def _profile() -> QualityProfile:
    return QualityProfile(
        profile_id="web-application-v1",
        version="1.0.0",
        requirements=(),
        allowed_trust=(ExecutionTrustClass.PR_UNTRUSTED,),
        recommended_execution=(ExecutionTarget.JENKINS,),
        critical_journey_e2e_required=True,
    )


def _manifest() -> RepositoryManifest:
    return RepositoryManifest(
        profile=ProfileBinding(
            profile_id="web-application-v1",
            version="1.0.0",
        ),
        behaviors_path="quality/behaviors.yaml",
        suites=(
            SuiteDefinition(
                suite_id="logic",
                entrypoint="test:logic",
                trust=ExecutionTrustClass.PR_UNTRUSTED,
                evidence_classes=(EvidenceClass.DETERMINISTIC,),
            ),
            SuiteDefinition(
                suite_id="browser",
                entrypoint="test:e2e",
                trust=ExecutionTrustClass.PR_UNTRUSTED,
                evidence_classes=(EvidenceClass.E2E,),
            ),
        ),
    )


def _behaviors() -> BehaviorDocument:
    return BehaviorDocument(
        behaviors=(
            Behavior(
                behavior_id="game.start",
                description="A game starts from a valid initial state.",
                criticality=Criticality.CRITICAL,
                required_evidence=(EvidenceClass.DETERMINISTIC,),
            ),
        ),
        critical_journeys=(
            CriticalJourney(
                journey_id="game.core",
                description="Player completes the core flow.",
                behavior_ids=("game.start",),
            ),
        ),
    )


def _inventory(*, include_e2e: bool) -> TestInventory:
    tests = [
        TestCaseObservation(
            test_id="vitest:tests/game.test.ts",
            framework="vitest",
            path="tests/game.test.ts",
            behavior_ids=("game.start",),
            evidence_class=EvidenceClass.DETERMINISTIC,
        )
    ]
    if include_e2e:
        tests.append(
            TestCaseObservation(
                test_id="playwright:e2e/game.spec.ts",
                framework="playwright",
                path="e2e/game.spec.ts",
                behavior_ids=("game.start",),
                evidence_class=EvidenceClass.E2E,
            )
        )
    return TestInventory(
        repository="setnessconsulting/game-example",
        sha="a" * 40,
        tests=tuple(tests),
    )


def test_guidance_says_no_new_test_when_current_evidence_is_proven() -> None:
    guidance = generate_agent_guidance(
        manifest=_manifest(),
        profile=_profile(),
        behaviors=_behaviors(),
        inventory=_inventory(include_e2e=True),
        affected_behavior_ids=("game.start",),
        gap_findings=(
            GapFinding(
                finding_id="gap:behavior",
                behavior_id="game.start",
                state=EvidenceState.PROVEN,
                reasons=("proven",),
            ),
            GapFinding(
                finding_id="gap:journey",
                behavior_id="journey:game.core",
                state=EvidenceState.PROVEN,
                reasons=("proven",),
            ),
        ),
    )

    assert guidance.new_test_needed is False
    assert "No new test is required" in guidance.next_actions[0]
    assert guidance.suite_ids_to_verify == ("browser", "logic")
    assert guidance.critical_journeys[0].journey_id == "game.core"


def test_changed_critical_journey_missing_e2e_requires_smallest_evidence_update() -> None:
    guidance = generate_agent_guidance(
        manifest=_manifest(),
        profile=_profile(),
        behaviors=_behaviors(),
        inventory=_inventory(include_e2e=False),
        affected_behavior_ids=("game.start",),
        gap_findings=(
            GapFinding(
                finding_id="gap:behavior",
                behavior_id="game.start",
                state=EvidenceState.PROVEN,
                reasons=("logic proven",),
            ),
            GapFinding(
                finding_id="gap:journey",
                behavior_id="journey:game.core",
                state=EvidenceState.MISSING,
                reasons=("end-to-end evidence missing",),
            ),
        ),
    )

    assert guidance.new_test_needed is True
    assert EvidenceClass.E2E in guidance.required_evidence
    assert "end-to-end" in " ".join(guidance.next_actions)
    assert "browser" in guidance.suite_ids_to_verify


def test_guidance_never_infers_unknown_affected_behavior() -> None:
    with pytest.raises(GuidanceError, match="not declared"):
        generate_agent_guidance(
            manifest=_manifest(),
            profile=_profile(),
            behaviors=_behaviors(),
            inventory=_inventory(include_e2e=True),
            affected_behavior_ids=("game.unknown",),
            gap_findings=(),
        )


def test_guidance_requires_complete_affected_gap_state() -> None:
    with pytest.raises(GuidanceError, match="complete"):
        generate_agent_guidance(
            manifest=_manifest(),
            profile=_profile(),
            behaviors=_behaviors(),
            inventory=_inventory(include_e2e=True),
            affected_behavior_ids=("game.start",),
            gap_findings=(
                GapFinding(
                    finding_id="gap:behavior",
                    behavior_id="game.start",
                    state=EvidenceState.PROVEN,
                    reasons=("proven",),
                ),
            ),
        )
