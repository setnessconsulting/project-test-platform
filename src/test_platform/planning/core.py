"""Deterministic execution-plan compilation from validated policy inputs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from test_platform.canonical import semantic_hash
from test_platform.contracts import (
    EvidenceClass,
    ExecutionPlan,
    ExecutionTrustClass,
    QualityProfile,
    RepositoryManifest,
    RequirementLevel,
    SuiteDefinition,
)
from test_platform.trust import (
    TRUST_RANK,
    TrustPolicyError,
    require_evidence_allowed_for_trust,
    require_live_qualification_context,
    require_profile_allows_trust,
)

_EXACT_SHA = re.compile(r"^[0-9a-f]{40,64}$")


class PlanningError(ValueError):
    """Raised when policy inputs cannot produce a safe deterministic plan."""


class ExecutionEvent(StrEnum):
    PULL_REQUEST = "pull-request"
    TRUSTED_BRANCH = "trusted-branch"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    LIVE_QUALIFICATION = "live-qualification"


_TRUST_RANK = TRUST_RANK


@dataclass(frozen=True)
class PlanningContext:
    """Non-contract execution context bound into a plan's semantic identity."""

    event: ExecutionEvent
    live_target: str | None = None
    owner_approved: bool = False


@dataclass(frozen=True)
class CompiledExecutionPlan:
    """Public ExecutionPlan plus the context that produced it."""

    plan: ExecutionPlan
    context: PlanningContext


def _required_profile_evidence(
    profile: QualityProfile,
    applicable_conditional_rules: frozenset[str],
) -> set[EvidenceClass]:
    required: set[EvidenceClass] = set()
    for requirement in profile.requirements:
        if requirement.level is RequirementLevel.REQUIRED or (
            requirement.level is RequirementLevel.CONDITIONAL
            and requirement.rule_id in applicable_conditional_rules
        ):
            required.add(requirement.evidence_class)
    if profile.critical_journey_e2e_required:
        required.add(EvidenceClass.E2E)
    return required


def _suite_allowed_at_trust(
    suite: SuiteDefinition,
    trust: ExecutionTrustClass,
) -> bool:
    return _TRUST_RANK[suite.trust] <= _TRUST_RANK[trust]


def compile_execution_plan(
    *,
    repository: str,
    sha: str,
    profile: QualityProfile,
    manifest: RepositoryManifest,
    trust: ExecutionTrustClass,
    policy_version: str,
    context: PlanningContext,
    behavior_evidence_classes: tuple[EvidenceClass, ...] = (),
    applicable_conditional_rules: frozenset[str] = frozenset(),
    additional_suite_ids: frozenset[str] = frozenset(),
) -> CompiledExecutionPlan:
    """Compile a bounded plan without executing repository-controlled commands."""
    if not _EXACT_SHA.fullmatch(sha):
        raise PlanningError("execution planning requires a full exact repository SHA")
    if not repository.strip():
        raise PlanningError("repository identity is required")
    if not policy_version.strip():
        raise PlanningError("policy version is required")

    expected_profile = manifest.profile
    if (
        expected_profile.profile_id != profile.profile_id
        or expected_profile.version != profile.version
    ):
        raise PlanningError("manifest profile binding does not match selected profile")

    try:
        require_profile_allows_trust(profile, trust)
        if trust is ExecutionTrustClass.LIVE_QUALIFICATION:
            require_live_qualification_context(
                trust=trust,
                sha=sha,
                target=context.live_target or "",
                owner_approved=context.owner_approved,
            )
    except TrustPolicyError as exc:
        raise PlanningError(str(exc)) from exc

    suites_by_id = {suite.suite_id: suite for suite in manifest.suites}
    unknown_requested = additional_suite_ids - set(suites_by_id)
    if unknown_requested:
        raise PlanningError(
            "additional suite IDs are not declared by the manifest: "
            + ", ".join(sorted(unknown_requested))
        )

    required_evidence = _required_profile_evidence(
        profile,
        applicable_conditional_rules,
    )
    required_evidence.update(behavior_evidence_classes)

    eligible = tuple(
        suite
        for suite in manifest.suites
        if _suite_allowed_at_trust(suite, trust)
    )

    selected_ids: set[str] = set(additional_suite_ids)
    for evidence_class in sorted(required_evidence, key=lambda item: item.value):
        providers = tuple(
            suite
            for suite in eligible
            if evidence_class in suite.evidence_classes
        )
        if not providers:
            raise PlanningError(
                f"no trust-compatible manifest suite provides required "
                f"{evidence_class.value} evidence"
            )
        selected_ids.update(item.suite_id for item in providers)

    selected = tuple(
        sorted(
            (suites_by_id[suite_id] for suite_id in selected_ids),
            key=lambda item: item.suite_id,
        )
    )

    for suite in selected:
        if not _suite_allowed_at_trust(suite, trust):
            raise PlanningError(
                f"suite {suite.suite_id} requires higher trust than {trust.value}"
            )
        try:
            require_evidence_allowed_for_trust(trust, suite.evidence_classes)
        except TrustPolicyError as exc:
            raise PlanningError(str(exc)) from exc

    semantic_payload = {
        "repository": repository,
        "sha": sha,
        "profile": manifest.profile.model_dump(mode="json"),
        "trust": trust.value,
        "policy_version": policy_version,
        "event": context.event.value,
        "live_target": context.live_target,
        "suites": [suite.model_dump(mode="json") for suite in selected],
    }
    plan = ExecutionPlan(
        plan_id=f"plan:{semantic_hash(semantic_payload)[:24]}",
        repository=repository,
        sha=sha,
        profile=manifest.profile,
        trust=trust,
        policy_version=policy_version,
        suites=selected,
    )
    return CompiledExecutionPlan(plan=plan, context=context)
