"""Fail-closed compilation of a canonical ExecutionPlan into a Jenkins request.

Everything a Jenkins adapter is allowed to believe about a run is decided
here, in Test Platform, before the request leaves this repository. The
compiler only ever narrows: it binds the exact repository and SHA, resolves
suites against the closed catalog, refuses unapproved entrypoints, refuses
capability and trust escalation, and fails closed on bounds.
"""

from __future__ import annotations

from test_platform.contracts import (
    EvidenceClass,
    ExecutionPlan,
    ExecutionTrustClass,
    ExecutorCapability,
    JenkinsCancellationPolicy,
    JenkinsConsumerContract,
    JenkinsExecutionMode,
    JenkinsExecutionRequest,
    JenkinsExpectedHead,
    JenkinsStaleHeadPolicy,
    JenkinsSuiteBinding,
    JenkinsTrustGrant,
    QualityResult,
    TrustCapability,
)
from test_platform.integration.outcomes import OUTCOME_RESULT_MAPPING
from test_platform.trust import TRUST_CAPABILITIES, TRUST_RANK


class JenkinsContractError(ValueError):
    """Raised when a plan cannot be bound to the Jenkins consumer contract."""


def _require_supported_plan_version(contract: JenkinsConsumerContract, plan: ExecutionPlan) -> None:
    """Fail closed on a plan schema version the contract does not support."""
    if plan.schema_version not in contract.plan_schema_versions:
        raise JenkinsContractError(
            f"unsupported execution plan schema version: {plan.schema_version}"
        )


def _require_supported_receipt_version(
    contract: JenkinsConsumerContract,
    schema_version: str,
) -> None:
    """Fail closed on a receipt schema version the contract does not support."""
    if schema_version not in contract.receipt_schema_versions:
        raise JenkinsContractError(
            f"unsupported quality receipt schema version: {schema_version}"
        )


def _require_repository_approved(
    contract: JenkinsConsumerContract,
    repository: str,
) -> None:
    """Require the plan's exact repository identity to be centrally approved."""
    if contract.repositories and repository not in contract.repositories:
        raise JenkinsContractError(
            f"repository {repository} is not approved by contract "
            f"{contract.contract_id}@{contract.contract_version}"
        )


def _resolve_bindings(
    contract: JenkinsConsumerContract,
    plan: ExecutionPlan,
) -> tuple[JenkinsSuiteBinding, ...]:
    """Resolve every planned suite against the closed catalog, fail closed."""
    if len(plan.suites) > contract.limits.max_suites:
        raise JenkinsContractError("execution plan exceeds the bounded suite count")

    catalog = {suite.suite_id: suite for suite in contract.suites}
    executors = {executor.executor_id: executor for executor in contract.executors}

    bindings: list[JenkinsSuiteBinding] = []
    for suite in plan.suites:
        binding = catalog.get(suite.suite_id)
        if binding is None:
            raise JenkinsContractError(
                f"suite {suite.suite_id} has no approved Jenkins executor mapping"
            )
        if binding.entrypoint != suite.entrypoint:
            raise JenkinsContractError(
                f"suite {suite.suite_id} declares entrypoint {suite.entrypoint} but the "
                f"approved Jenkins mapping is {binding.entrypoint}"
            )
        if suite.timeout_seconds > binding.timeout_seconds:
            raise JenkinsContractError(
                f"suite {suite.suite_id} timeout {suite.timeout_seconds}s exceeds the "
                f"approved bounded timeout {binding.timeout_seconds}s"
            )
        if TRUST_RANK[suite.trust] > TRUST_RANK[plan.trust]:
            raise JenkinsContractError(
                f"suite {suite.suite_id} requires higher trust than {plan.trust.value}"
            )
        undeclared = sorted(
            item.value
            for item in suite.evidence_classes
            if item not in binding.evidence_classes
        )
        if undeclared:
            raise JenkinsContractError(
                f"suite {suite.suite_id} claims unapproved evidence classes: "
                + ", ".join(undeclared)
            )
        executor = executors[binding.executor_id]
        if TRUST_RANK[plan.trust] > TRUST_RANK[executor.max_trust]:
            raise JenkinsContractError(
                f"executor {executor.executor_id} cannot execute trust class "
                f"{plan.trust.value}"
            )
        missing = sorted(
            item.value
            for item in binding.required_capabilities
            if item not in executor.capabilities
        )
        if missing:
            raise JenkinsContractError(
                f"executor {executor.executor_id} lacks required capabilities: "
                + ", ".join(missing)
            )
        bindings.append(binding)

    return tuple(bindings)


def _required_capabilities(
    bindings: tuple[JenkinsSuiteBinding, ...],
) -> tuple[ExecutorCapability, ...]:
    """Return the bounded union of approved suite capability requirements."""
    required: set[ExecutorCapability] = set()
    for binding in bindings:
        required.update(binding.required_capabilities)
    return tuple(sorted(required, key=lambda item: item.value))


def _require_live_evidence_permitted(
    plan: ExecutionPlan,
    bindings: tuple[JenkinsSuiteBinding, ...],
) -> None:
    """Refuse live artifact declarations without live-qualification trust."""
    if plan.trust is ExecutionTrustClass.LIVE_QUALIFICATION:
        return
    live_suites = sorted(
        binding.suite_id
        for binding in bindings
        if any(artifact.live for artifact in binding.artifacts)
        or EvidenceClass.LIVE in binding.evidence_classes
    )
    if live_suites:
        raise JenkinsContractError(
            "live qualification surfaces require live-qualification trust: "
            + ", ".join(live_suites)
        )


def _trust_grant(plan: ExecutionPlan) -> JenkinsTrustGrant:
    """Bind the maximum capability ceiling the plan's trust class permits."""
    capabilities = tuple(
        sorted(TRUST_CAPABILITIES[plan.trust], key=lambda item: item.value)
    )
    return JenkinsTrustGrant(trust=plan.trust, capabilities=capabilities)


def _max_execution_seconds(
    contract: JenkinsConsumerContract,
    bindings: tuple[JenkinsSuiteBinding, ...],
) -> int:
    """Bound total execution time by the sequential sum of approved timeouts."""
    total = sum(binding.timeout_seconds for binding in bindings)
    return min(total, contract.limits.max_execution_seconds)


def compile_jenkins_execution_request(
    plan: ExecutionPlan,
    contract: JenkinsConsumerContract,
    *,
    execution_mode: JenkinsExecutionMode = JenkinsExecutionMode.SYNTHETIC_QUALIFICATION,
    cancellation: JenkinsCancellationPolicy | None = None,
    stale_head: JenkinsStaleHeadPolicy | None = None,
) -> JenkinsExecutionRequest:
    """Compile a canonical plan into the versioned Jenkins execution request.

    The result contains structured, centrally approved data only. It never
    contains a command, a credential, a token, or a repository-supplied
    instruction that the adapter would have to interpret.
    """
    _require_supported_plan_version(contract, plan)
    _require_supported_receipt_version(contract, "1")
    _require_repository_approved(contract, plan.repository)

    bindings = _resolve_bindings(contract, plan)
    _require_live_evidence_permitted(plan, bindings)

    if stale_head is not None and str(stale_head.on_stale_head) not in {
        QualityResult.BLOCKED.value,
        QualityResult.NOT_EVALUABLE.value,
    }:
        raise JenkinsContractError("stale head handling can never resolve to a pass")

    return JenkinsExecutionRequest(
        contract_id=contract.contract_id,
        contract_version=contract.contract_version,
        plan_schema_version=plan.schema_version,
        policy_version=plan.policy_version,
        execution_mode=execution_mode,
        head=JenkinsExpectedHead(repository=plan.repository, sha=plan.sha),
        plan=plan,
        trust_grant=_trust_grant(plan),
        suites=bindings,
        required_capabilities=_required_capabilities(bindings),
        result_mapping=OUTCOME_RESULT_MAPPING,
        cancellation=cancellation or JenkinsCancellationPolicy(),
        stale_head=stale_head or JenkinsStaleHeadPolicy(),
        max_execution_seconds=_max_execution_seconds(contract, bindings),
    )


def grant_allows(grant: JenkinsTrustGrant, capability: TrustCapability) -> bool:
    """Return whether a compiled trust grant permits a capability."""
    return capability in grant.capabilities
