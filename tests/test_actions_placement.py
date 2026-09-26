from __future__ import annotations

from test_platform.contracts import WorkflowPlacement
from test_platform.planning.actions import (
    WorkflowObservation,
    analyze_actions_placement,
)


def test_roles_drive_placement_instead_of_cost() -> None:
    report = analyze_actions_placement(
        (
            WorkflowObservation(
                workflow_id="ci",
                evidence_intent=("build", "test"),
                verification=True,
                equivalent_plan_coverage=True,
                jenkins_capable=True,
                hosted_minutes=120.0,
                usage_complete=True,
            ),
            WorkflowObservation(
                workflow_id="deploy",
                evidence_intent=("deploy",),
                deployment=True,
                hosted_minutes=600.0,
                usage_complete=True,
            ),
            WorkflowObservation(
                workflow_id="codeql",
                evidence_intent=("security-scan",),
                security_native=True,
                hosted_minutes=300.0,
                usage_complete=True,
            ),
        )
    )

    decisions = {item.workflow_id: item.placement for item in report.decisions}
    assert decisions == {
        "ci": WorkflowPlacement.MOVE_TO_JENKINS,
        "codeql": WorkflowPlacement.RETAIN_GITHUB,
        "deploy": WorkflowPlacement.RETAIN_DEPLOYMENT,
    }
    assert report.hosted_verification_minutes == 120.0
    assert report.hosted_deployment_minutes == 600.0
    assert report.candidate_moved_minutes == 120.0


def test_incomplete_usage_never_creates_savings_claim() -> None:
    report = analyze_actions_placement(
        (
            WorkflowObservation(
                workflow_id="ci",
                evidence_intent=("test",),
                verification=True,
                equivalent_plan_coverage=True,
                jenkins_capable=True,
                hosted_minutes=12.0,
                usage_complete=False,
            ),
        )
    )

    assert report.hosted_verification_minutes is None
    assert report.candidate_moved_minutes is None


def test_duplicate_requires_same_evidence_intent_not_similar_name() -> None:
    report = analyze_actions_placement(
        (
            WorkflowObservation(
                workflow_id="ci",
                evidence_intent=("build", "test"),
                verification=True,
            ),
            WorkflowObservation(
                workflow_id="ci-copy",
                evidence_intent=("deploy",),
                verification=True,
                duplicate_of="ci",
                equivalent_plan_coverage=True,
            ),
        )
    )

    decision = next(item for item in report.decisions if item.workflow_id == "ci-copy")
    assert decision.placement is WorkflowPlacement.NOT_EVALUATED


def test_manual_fallback_is_deliberately_retained() -> None:
    report = analyze_actions_placement(
        (
            WorkflowObservation(
                workflow_id="clean-room",
                evidence_intent=("build", "test"),
                verification=True,
                manual_fallback=True,
            ),
        )
    )

    assert report.decisions[0].placement is WorkflowPlacement.MANUAL_FALLBACK
