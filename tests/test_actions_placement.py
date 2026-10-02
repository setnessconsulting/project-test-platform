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
        # Unqualified deployment fails closed; it is never retained as
        # routine GitHub-hosted deployment solely because it deploys.
        "deploy": WorkflowPlacement.NOT_EVALUATED,
    }
    assert report.hosted_verification_minutes == 120.0
    assert report.hosted_deployment_minutes == 600.0
    assert report.candidate_moved_minutes == 120.0


def test_qualified_cloudflare_deployment_migrates_to_jenkins() -> None:
    report = analyze_actions_placement(
        (
            WorkflowObservation(
                workflow_id="deploy-cloudflare",
                evidence_intent=("deploy", "cloudflare-workers:production"),
                deployment=True,
                equivalent_plan_coverage=True,
                jenkins_capable=True,
                deployment_provider_target="cloudflare-workers:production",
                deployment_trusted_context=True,
                deployment_exact_sha=True,
                deployment_verification_gate=True,
                deployment_credentials_scoped=True,
                deployment_readback=True,
                deployment_rollback=True,
                hosted_minutes=45.0,
                usage_complete=True,
            ),
        )
    )

    assert report.decisions[0].placement is (
        WorkflowPlacement.MOVE_DEPLOYMENT_TO_JENKINS
    )
    # Deployment migration must not be misattributed as verification savings.
    assert report.hosted_deployment_minutes == 45.0
    assert report.candidate_moved_minutes is None


def test_incomplete_deployment_prerequisites_fail_closed() -> None:
    for missing in (
        {"deployment_trusted_context": False},
        {"deployment_exact_sha": False},
        {"deployment_verification_gate": False},
        {"deployment_credentials_scoped": False},
        {"deployment_readback": False},
        {"deployment_rollback": False},
        {"deployment_provider_target": None},
        {"jenkins_capable": False},
        {"equivalent_plan_coverage": False},
    ):
        kwargs: dict[str, object] = {
            "workflow_id": "deploy-partial",
            "evidence_intent": ("deploy",),
            "deployment": True,
            "equivalent_plan_coverage": True,
            "jenkins_capable": True,
            "deployment_provider_target": "vercel:production",
            "deployment_trusted_context": True,
            "deployment_exact_sha": True,
            "deployment_verification_gate": True,
            "deployment_credentials_scoped": True,
            "deployment_readback": True,
            "deployment_rollback": True,
        }
        kwargs.update(missing)  # type: ignore[typeddict-item]
        report = analyze_actions_placement((WorkflowObservation(**kwargs),))  # type: ignore[arg-type]
        assert report.decisions[0].placement is WorkflowPlacement.NOT_EVALUATED


def test_native_and_fallback_lanes_stay_distinct_from_deployment() -> None:
    report = analyze_actions_placement(
        (
            WorkflowObservation(
                workflow_id="deploy-native",
                evidence_intent=("deploy",),
                deployment=True,
                security_native=True,
                equivalent_plan_coverage=True,
                jenkins_capable=True,
                deployment_provider_target="cloudflare-pages:production",
                deployment_trusted_context=True,
                deployment_exact_sha=True,
                deployment_verification_gate=True,
                deployment_credentials_scoped=True,
                deployment_readback=True,
                deployment_rollback=True,
            ),
            WorkflowObservation(
                workflow_id="deploy-fallback",
                evidence_intent=("deploy",),
                deployment=True,
                manual_fallback=True,
                equivalent_plan_coverage=True,
                jenkins_capable=True,
                deployment_provider_target="cloudflare-pages:production",
                deployment_trusted_context=True,
                deployment_exact_sha=True,
                deployment_verification_gate=True,
                deployment_credentials_scoped=True,
                deployment_readback=True,
                deployment_rollback=True,
            ),
        )
    )
    decisions = {item.workflow_id: item.placement for item in report.decisions}
    assert decisions == {
        "deploy-native": WorkflowPlacement.RETAIN_GITHUB,
        "deploy-fallback": WorkflowPlacement.MANUAL_FALLBACK,
    }


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
