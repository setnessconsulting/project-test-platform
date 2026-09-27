"""Fail-closed ingestion of a Jenkins receipt submission.

Test Platform never trusts a consumer to describe what happened. Every
returned receipt is re-derived from the approved request and the consumer's
own normalized outcome, and any divergence is rejected before the receipt can
influence quality evaluation.
"""

from __future__ import annotations

from collections.abc import Collection

from test_platform.contracts import (
    Diagnostic,
    DiagnosticSeverity,
    EvidenceClass,
    EvidenceOrigin,
    EvidenceReference,
    ExecutionTrustClass,
    JenkinsConsumerContract,
    JenkinsDiagnostic,
    JenkinsExecutionMode,
    JenkinsExecutionRequest,
    JenkinsExecutionStatus,
    JenkinsObservedHead,
    JenkinsReceiptSubmission,
    JenkinsSuiteBinding,
    JenkinsSuiteOutcome,
    QualityReceipt,
    QualityResult,
    ToolVersion,
)
from test_platform.evidence.receipts import (
    ReceiptError,
    build_quality_receipt,
    validate_quality_receipt,
)
from test_platform.integration.outcomes import OUTCOME_DESCRIPTIONS
from test_platform.trust import TRUST_RANK


class ReceiptIngestError(ValueError):
    """Raised when a consumer submission cannot be accepted as evidence."""


def _require_contract_identity(
    request: JenkinsExecutionRequest,
    contract: JenkinsConsumerContract,
    submission: JenkinsReceiptSubmission,
) -> None:
    """Fail closed on an unknown or mismatched consumer contract version."""
    if submission.contract_id != request.contract_id:
        raise ReceiptIngestError("submission contract ID does not match the request")
    if submission.contract_version != request.contract_version:
        raise ReceiptIngestError(
            "submission contract version does not match the request"
        )
    if contract.contract_id != request.contract_id:
        raise ReceiptIngestError("contract ID does not match the request")
    if contract.contract_version != request.contract_version:
        raise ReceiptIngestError(
            "contract version does not match the request; the consumer must be "
            "re-qualified against this contract before its evidence is accepted"
        )
    if submission.schema_version not in contract.receipt_schema_versions:
        raise ReceiptIngestError(
            f"unsupported submission schema version: {submission.schema_version}"
        )


def _require_plan_binding(
    request: JenkinsExecutionRequest,
    submission: JenkinsReceiptSubmission,
) -> None:
    """Fail closed unless the submission is bound to the exact plan identity."""
    if submission.plan_id != request.plan.plan_id:
        raise ReceiptIngestError("submission plan identity does not match the request")
    if submission.head.repository != request.plan.repository:
        raise ReceiptIngestError("submission repository does not match the plan")
    if submission.head.sha != request.plan.sha:
        raise ReceiptIngestError("submission exact SHA does not match the plan")
    if submission.execution_mode != request.execution_mode:
        raise ReceiptIngestError("submission execution mode does not match the request")


_HEAD_DEPENDENT_STATUSES = frozenset(
    {
        JenkinsExecutionStatus.STALE_HEAD,
        JenkinsExecutionStatus.CHECKOUT_SHA_MISMATCH,
        JenkinsExecutionStatus.CANCELLED,
    }
)


def _require_observed_head(
    request: JenkinsExecutionRequest,
    observed: JenkinsObservedHead,
    suite_id: str,
    status: JenkinsExecutionStatus,
) -> None:
    """Fail closed on repository divergence and unbound head claims.

    A foreign observed head is only ever reported through the head-dependent
    normalized statuses, which explicitly signal "not evidence for the bound
    head" and can never normalize to a pass. Any other status observed at a
    different SHA is a binding failure.
    """
    if observed.repository != request.head.repository:
        raise ReceiptIngestError(
            f"suite {suite_id} observed a different repository than the plan"
        )
    if observed.sha == request.head.sha:
        return
    if status not in _HEAD_DEPENDENT_STATUSES:
        raise ReceiptIngestError(
            f"suite {suite_id} observed SHA {observed.sha} but the plan binds "
            f"{request.head.sha}"
        )


def _require_live_evidence_permitted(
    request: JenkinsExecutionRequest,
    submission: JenkinsReceiptSubmission,
    evidence: Collection[EvidenceReference],
) -> None:
    """Keep synthetic and controller-recorded evidence out of live claims."""
    if not any(item.live for item in evidence):
        return
    if (
        request.plan.trust is not ExecutionTrustClass.LIVE_QUALIFICATION
        or request.execution_mode is not JenkinsExecutionMode.CONTROLLER_EXECUTION
        or submission.evidence_origin is not EvidenceOrigin.LIVE
    ):
        raise ReceiptIngestError(
            "live evidence requires live-qualification trust, a controller "
            "execution mode, and a live evidence origin"
        )


def _require_evidence_bounded(
    request: JenkinsExecutionRequest,
    contract: JenkinsConsumerContract,
    binding: JenkinsSuiteBinding,
    evidence: tuple[EvidenceReference, ...],
) -> None:
    """Bound evidence volume and keep references inside the declared handoff."""
    if len(evidence) > contract.limits.max_evidence_references_per_suite:
        raise ReceiptIngestError(
            f"suite {binding.suite_id} exceeds the bounded evidence reference count"
        )
    declared = {artifact.path for artifact in binding.artifacts}
    for item in evidence:
        if not item.reference:
            continue
        if item.reference.startswith("/") or ".." in item.reference.split("/"):
            raise ReceiptIngestError(
                f"suite {binding.suite_id} declared an unbounded evidence reference"
            )
        if item.reference not in declared:
            raise ReceiptIngestError(
                f"suite {binding.suite_id} handed off undeclared evidence "
                f"{item.reference}"
            )
        if item.live and not any(
            artifact.live and artifact.path == item.reference
            for artifact in binding.artifacts
        ):
            raise ReceiptIngestError(
                f"suite {binding.suite_id} marked undeclared evidence as live"
            )


def _expected_result(
    request: JenkinsExecutionRequest,
    submission: JenkinsReceiptSubmission,
    suite_id: str,
    status: JenkinsExecutionStatus,
) -> QualityResult:
    """Resolve the normalized result from the request's authoritative mapping."""
    try:
        result = request.result_for(status)
    except ValueError as exc:
        raise ReceiptIngestError(str(exc)) from exc
    if status is JenkinsExecutionStatus.STALE_HEAD and request.stale_head.require_current_head:
        allowed = (
            QualityResult.BLOCKED
            if str(request.stale_head.on_stale_head) == QualityResult.BLOCKED.value
            else QualityResult.NOT_EVALUABLE
        )
        if result is not allowed:
            raise ReceiptIngestError(
                f"suite {suite_id} reported a stale head as {result.value}"
            )
    return result


def _expected_receipt(
    request: JenkinsExecutionRequest,
    submission: JenkinsReceiptSubmission,
    binding: JenkinsSuiteBinding,
    outcome: JenkinsSuiteOutcome,
) -> QualityReceipt:
    """Re-derive the canonical receipt so a consumer cannot forge one."""
    result = _expected_result(request, submission, binding.suite_id, outcome.status)
    return build_quality_receipt(
        plan=request.plan,
        suite_id=binding.suite_id,
        executor=binding.executor_id,
        result=result,
        passed_tests=outcome.receipt.passed_tests,
        failed_tests=outcome.receipt.failed_tests,
        skipped_tests=outcome.receipt.skipped_tests,
        duration_seconds=outcome.receipt.duration_seconds,
        evidence=outcome.receipt.evidence,
        tool_versions=outcome.receipt.tool_versions,
        generated_at=outcome.receipt.generated_at,
    )


def _require_receipt_reproduced(
    expected: QualityReceipt,
    submitted: QualityReceipt,
    suite_id: str,
) -> None:
    """Require byte-for-byte agreement on receipt identity and content."""
    if expected.semantic_payload() != submitted.semantic_payload():
        raise ReceiptIngestError(
            f"suite {suite_id} receipt does not match the deterministic result "
            "derived from its normalized outcome"
        )


def _require_trust_not_escalated(
    request: JenkinsExecutionRequest,
    contract: JenkinsConsumerContract,
    binding: JenkinsSuiteBinding,
    trust: ExecutionTrustClass,
) -> None:
    """Refuse a receipt that claims more trust than the request granted."""
    if TRUST_RANK[trust] > TRUST_RANK[request.plan.trust]:
        raise ReceiptIngestError(
            f"suite {binding.suite_id} escalated trust beyond the plan trust class"
        )
    executors = {executor.executor_id: executor for executor in contract.executors}
    executor = executors.get(binding.executor_id)
    if executor is None:
        raise ReceiptIngestError(
            f"suite {binding.suite_id} has no approved executor mapping"
        )
    if TRUST_RANK[request.plan.trust] > TRUST_RANK[executor.max_trust]:
        raise ReceiptIngestError(
            f"suite {binding.suite_id} requested trust beyond the executor ceiling"
        )


def _require_suite_covered(
    request: JenkinsExecutionRequest,
    submission: JenkinsReceiptSubmission,
) -> None:
    """Require exactly one outcome per planned suite, so nothing is dropped."""
    planned = [suite.suite_id for suite in request.plan.suites]
    reported = [outcome.suite_id for outcome in submission.outcomes]
    if sorted(reported) != sorted(planned):
        raise ReceiptIngestError(
            "submission must report exactly one outcome per planned suite"
        )


def _require_diagnostics_bounded(
    contract: JenkinsConsumerContract,
    suite_id: str,
    diagnostics: tuple[JenkinsDiagnostic, ...],
) -> None:
    """Bound diagnostic count and message length for every outcome."""
    if len(diagnostics) > contract.limits.max_diagnostics_per_outcome:
        raise ReceiptIngestError(
            f"suite {suite_id} exceeds the bounded diagnostic count"
        )
    for diagnostic in diagnostics:
        if len(diagnostic.message) > contract.limits.max_diagnostic_message_length:
            raise ReceiptIngestError(
                f"suite {suite_id} diagnostic message exceeds the bounded length"
            )


def _promoted_diagnostics(submission: JenkinsReceiptSubmission) -> tuple[Diagnostic, ...]:
    """Translate bounded consumer diagnostics into canonical platform diagnostics."""
    promoted: list[Diagnostic] = []
    for outcome in submission.outcomes:
        for diagnostic in outcome.diagnostics:
            promoted.append(
                Diagnostic(
                    code=f"jenkins.{diagnostic.code}",
                    severity=diagnostic.severity,
                    message=diagnostic.message,
                )
            )
    return tuple(promoted)


def ingest_jenkins_receipt_submission(
    request: JenkinsExecutionRequest,
    submission: JenkinsReceiptSubmission,
    contract: JenkinsConsumerContract,
    *,
    seen_receipt_ids: Collection[str] = (),
) -> tuple[tuple[QualityReceipt, ...], tuple[Diagnostic, ...]]:
    """Validate a consumer submission and return canonical receipts.

    Any divergence between the submission and the approved request, the
    contract catalog, or the deterministic re-derivation of the receipt raises
    ``ReceiptIngestError`` and yields no evidence.
    """
    _require_contract_identity(request, contract, submission)
    _require_plan_binding(request, submission)
    _require_suite_covered(request, submission)

    bindings = {binding.suite_id: binding for binding in request.suites}
    receipts: list[QualityReceipt] = []
    for outcome in submission.outcomes:
        binding = bindings[outcome.suite_id]
        _require_observed_head(
            request, outcome.observed_head, outcome.suite_id, outcome.status
        )
        _require_diagnostics_bounded(contract, outcome.suite_id, outcome.diagnostics)
        _require_evidence_bounded(
            request,
            contract,
            binding,
            outcome.receipt.evidence,
        )
        _require_live_evidence_permitted(
            request,
            submission,
            outcome.receipt.evidence,
        )
        _require_trust_not_escalated(
            request,
            contract,
            binding,
            outcome.receipt.trust,
        )
        if outcome.executor_id != binding.executor_id:
            raise ReceiptIngestError(
                f"suite {outcome.suite_id} reported an unapproved executor"
            )
        if outcome.receipt.repository != request.plan.repository:
            raise ReceiptIngestError(
                f"suite {outcome.suite_id} receipt repository does not match the plan"
            )
        if outcome.receipt.sha != request.plan.sha:
            raise ReceiptIngestError(
                f"suite {outcome.suite_id} receipt SHA does not match the plan"
            )
        if outcome.receipt.profile != request.plan.profile:
            raise ReceiptIngestError(
                f"suite {outcome.suite_id} receipt profile does not match the plan"
            )
        if outcome.receipt.trust is not request.plan.trust:
            raise ReceiptIngestError(
                f"suite {outcome.suite_id} receipt trust class does not match the plan"
            )
        _require_evidence_classes_approved(binding, outcome.suite_id, outcome.receipt)

        expected = _expected_receipt(request, submission, binding, outcome)
        _require_receipt_reproduced(expected, outcome.receipt, outcome.suite_id)
        try:
            validate_quality_receipt(
                request.plan,
                outcome.receipt,
                seen_receipt_ids=seen_receipt_ids,
            )
        except ReceiptError as exc:
            raise ReceiptIngestError(str(exc)) from exc
        receipts.append(outcome.receipt)

    return tuple(receipts), _promoted_diagnostics(submission)


def _require_evidence_classes_approved(
    binding: JenkinsSuiteBinding,
    suite_id: str,
    receipt: QualityReceipt,
) -> None:
    """Refuse evidence classes the approved binding does not declare."""
    approved = set(binding.evidence_classes)
    for item in receipt.evidence:
        if item.evidence_class not in approved:
            raise ReceiptIngestError(
                f"suite {suite_id} claimed unapproved evidence class "
                f"{item.evidence_class.value}"
            )
    if EvidenceClass.LIVE in approved and receipt.trust is not (
        ExecutionTrustClass.LIVE_QUALIFICATION
    ):
        raise ReceiptIngestError(
            f"suite {suite_id} live evidence requires live-qualification trust"
        )


def outcome_diagnostic(status: JenkinsExecutionStatus) -> tuple[Diagnostic, ...]:
    """Build the canonical diagnostic describing a normalized outcome."""
    severity = (
        DiagnosticSeverity.INFO
        if status is JenkinsExecutionStatus.PASSED
        else DiagnosticSeverity.WARNING
    )
    return (
        Diagnostic(
            code=f"jenkins.outcome.{status.value}",
            severity=severity,
            message=OUTCOME_DESCRIPTIONS[status],
        ),
    )


def declared_tool_versions(versions: tuple[tuple[str, str], ...]) -> tuple[ToolVersion, ...]:
    """Build bounded canonical tool versions from approved executor facts."""
    return tuple(ToolVersion(name=name, version=version) for name, version in versions)
