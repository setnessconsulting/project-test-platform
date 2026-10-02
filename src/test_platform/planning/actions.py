"""Evidence-based GitHub Actions execution-placement analysis."""

from __future__ import annotations

from dataclasses import dataclass

from test_platform.contracts import (
    WorkflowPlacement,
    WorkflowPlacementDecision,
)


@dataclass(frozen=True)
class WorkflowObservation:
    """Sanitized workflow facts supplied by a trusted repository/GitHub observer."""

    workflow_id: str
    evidence_intent: tuple[str, ...]
    verification: bool = False
    deployment: bool = False
    github_native: bool = False
    security_native: bool = False
    manual_fallback: bool = False
    equivalent_plan_coverage: bool = False
    jenkins_capable: bool = False
    duplicate_of: str | None = None
    hosted_minutes: float | None = None
    usage_complete: bool = False
    # Deployment-migration prerequisites (API-401). All default to the
    # fail-closed state. Provider/deployment architecture authority remains
    # external to Test Platform; these fields record that the external
    # prerequisites have been observed, never that Test Platform deploys.
    deployment_provider_target: str | None = None
    deployment_trusted_context: bool = False
    deployment_exact_sha: bool = False
    deployment_verification_gate: bool = False
    deployment_credentials_scoped: bool = False
    deployment_readback: bool = False
    deployment_rollback: bool = False


@dataclass(frozen=True)
class ActionsPlacementReport:
    """Placement decisions plus savings inputs without speculative minute claims."""

    decisions: tuple[WorkflowPlacementDecision, ...]
    hosted_verification_minutes: float | None
    hosted_deployment_minutes: float | None
    candidate_moved_minutes: float | None


def _deployment_migration_ready(workflow: WorkflowObservation) -> bool:
    """Return whether all deterministic deployment-migration prerequisites hold."""
    return bool(
        workflow.jenkins_capable
        and workflow.equivalent_plan_coverage
        and workflow.deployment_trusted_context
        and workflow.deployment_exact_sha
        and workflow.deployment_provider_target
        and workflow.deployment_verification_gate
        and workflow.deployment_credentials_scoped
        and workflow.deployment_readback
        and workflow.deployment_rollback
    )


def classify_workflow(
    workflow: WorkflowObservation,
    *,
    observations_by_id: dict[str, WorkflowObservation],
) -> WorkflowPlacementDecision:
    """Classify workflow placement from role/equivalence evidence, never from cost alone."""
    if workflow.github_native or workflow.security_native:
        placement = WorkflowPlacement.RETAIN_GITHUB
        reason = "workflow depends on GitHub-native or security-hosted capability"
    elif workflow.manual_fallback:
        placement = WorkflowPlacement.MANUAL_FALLBACK
        reason = "workflow is an explicit owner-controlled fallback lane"
    elif workflow.duplicate_of is not None:
        original = observations_by_id.get(workflow.duplicate_of)
        same_intent = (
            original is not None
            and tuple(sorted(original.evidence_intent))
            == tuple(sorted(workflow.evidence_intent))
        )
        if same_intent and workflow.equivalent_plan_coverage:
            placement = WorkflowPlacement.REMOVE_DUPLICATE
            reason = "explicit duplicate has equivalent evidence intent and plan coverage"
        else:
            placement = WorkflowPlacement.NOT_EVALUATED
            reason = "duplicate claim lacks equivalent evidence intent or plan coverage"
    elif workflow.deployment:
        if _deployment_migration_ready(workflow):
            placement = WorkflowPlacement.MOVE_DEPLOYMENT_TO_JENKINS
            reason = (
                "routine deployment migrates to Jenkins; provider authority "
                "remains external, execution requires trusted context, exact "
                "SHA, provider target, verification gate, scoped credentials, "
                "read-back and rollback"
            )
        else:
            placement = WorkflowPlacement.NOT_EVALUATED
            reason = (
                "deployment lacks qualified Jenkins migration prerequisites "
                "(trusted context, exact SHA, provider target, verification "
                "gate, scoped credentials, read-back, rollback); fail closed"
            )
    elif (
        workflow.verification
        and workflow.equivalent_plan_coverage
        and workflow.jenkins_capable
    ):
        placement = WorkflowPlacement.MOVE_TO_JENKINS
        reason = "routine verification has equivalent Test Platform plan coverage"
    elif workflow.verification:
        placement = WorkflowPlacement.NOT_EVALUATED
        reason = "verification lacks qualified equivalent Jenkins/plan evidence"
    else:
        placement = WorkflowPlacement.NOT_EVALUATED
        reason = "workflow role is not sufficiently classified"

    return WorkflowPlacementDecision(
        workflow_id=workflow.workflow_id,
        placement=placement,
        reason=reason,
    )


def analyze_actions_placement(
    observations: tuple[WorkflowObservation, ...],
) -> ActionsPlacementReport:
    """Produce deterministic placement decisions and only complete minute totals."""
    by_id = {item.workflow_id: item for item in observations}
    if len(by_id) != len(observations):
        raise ValueError("workflow IDs must be unique")

    decisions = tuple(
        sorted(
            (
                classify_workflow(item, observations_by_id=by_id)
                for item in observations
            ),
            key=lambda item: item.workflow_id,
        )
    )
    decision_by_id = {item.workflow_id: item for item in decisions}

    verification_rows = tuple(item for item in observations if item.verification)
    deployment_rows = tuple(item for item in observations if item.deployment)

    verification_complete = all(
        item.usage_complete and item.hosted_minutes is not None
        for item in verification_rows
    )
    deployment_complete = all(
        item.usage_complete and item.hosted_minutes is not None
        for item in deployment_rows
    )

    hosted_verification = (
        sum(item.hosted_minutes or 0.0 for item in verification_rows)
        if verification_rows and verification_complete
        else None
    )
    hosted_deployment = (
        sum(item.hosted_minutes or 0.0 for item in deployment_rows)
        if deployment_rows and deployment_complete
        else None
    )

    moved_rows = tuple(
        item
        for item in verification_rows
        if decision_by_id[item.workflow_id].placement
        in {
            WorkflowPlacement.MOVE_TO_JENKINS,
            WorkflowPlacement.REMOVE_DUPLICATE,
        }
    )
    moved_complete = bool(moved_rows) and all(
        item.usage_complete and item.hosted_minutes is not None
        for item in moved_rows
    )
    candidate_moved = (
        sum(item.hosted_minutes or 0.0 for item in moved_rows)
        if moved_complete
        else None
    )

    return ActionsPlacementReport(
        decisions=decisions,
        hosted_verification_minutes=hosted_verification,
        hosted_deployment_minutes=hosted_deployment,
        candidate_moved_minutes=candidate_moved,
    )
