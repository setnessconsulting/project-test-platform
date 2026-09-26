from __future__ import annotations

import pytest

from test_platform.contracts import (
    EvidenceClass,
    ExecutionTarget,
    ExecutionTrustClass,
    ProfileBinding,
    ProfileRequirement,
    QualityProfile,
    RepositoryManifest,
    RequirementLevel,
    SuiteDefinition,
)
from test_platform.planning.core import (
    ExecutionEvent,
    PlanningContext,
    PlanningError,
    compile_execution_plan,
)


def _profile() -> QualityProfile:
    return QualityProfile(
        profile_id="web-application-v1",
        version="1.0.0",
        requirements=(
            ProfileRequirement(
                rule_id="static-verification",
                evidence_class=EvidenceClass.STATIC,
                level=RequirementLevel.REQUIRED,
                description="Static verification required.",
            ),
            ProfileRequirement(
                rule_id="browser-e2e",
                evidence_class=EvidenceClass.E2E,
                level=RequirementLevel.REQUIRED,
                non_waivable=True,
                description="Critical browser journey required.",
            ),
        ),
        allowed_trust=(
            ExecutionTrustClass.PR_UNTRUSTED,
            ExecutionTrustClass.TRUSTED_BRANCH,
        ),
        recommended_execution=(ExecutionTarget.JENKINS,),
        critical_journey_e2e_required=True,
    )


def _manifest() -> RepositoryManifest:
    return RepositoryManifest(
        profile=ProfileBinding(profile_id="web-application-v1", version="1.0.0"),
        behaviors_path="quality/behaviors.yaml",
        suites=(
            SuiteDefinition(
                suite_id="static",
                entrypoint="verify:static",
                trust=ExecutionTrustClass.PR_UNTRUSTED,
                evidence_classes=(EvidenceClass.STATIC,),
            ),
            SuiteDefinition(
                suite_id="e2e",
                entrypoint="test:e2e",
                trust=ExecutionTrustClass.PR_UNTRUSTED,
                evidence_classes=(EvidenceClass.E2E,),
            ),
        ),
    )


def test_plan_selects_every_suite_needed_for_required_evidence() -> None:
    first = compile_execution_plan(
        repository="setnessconsulting/web-example",
        sha="a" * 40,
        profile=_profile(),
        manifest=_manifest(),
        trust=ExecutionTrustClass.PR_UNTRUSTED,
        policy_version="1",
        context=PlanningContext(event=ExecutionEvent.PULL_REQUEST),
    )
    second = compile_execution_plan(
        repository="setnessconsulting/web-example",
        sha="a" * 40,
        profile=_profile(),
        manifest=_manifest(),
        trust=ExecutionTrustClass.PR_UNTRUSTED,
        policy_version="1",
        context=PlanningContext(event=ExecutionEvent.PULL_REQUEST),
    )

    assert first == second
    assert [suite.suite_id for suite in first.plan.suites] == ["e2e", "static"]
    assert first.plan.plan_id == second.plan.plan_id


def test_plan_cannot_skip_required_evidence_for_changed_scope_optimization() -> None:
    manifest = RepositoryManifest(
        profile=_manifest().profile,
        behaviors_path="quality/behaviors.yaml",
        suites=(_manifest().suites[0],),
    )
    with pytest.raises(PlanningError, match="end-to-end"):
        compile_execution_plan(
            repository="setnessconsulting/web-example",
            sha="b" * 40,
            profile=_profile(),
            manifest=manifest,
            trust=ExecutionTrustClass.PR_UNTRUSTED,
            policy_version="1",
            context=PlanningContext(event=ExecutionEvent.PULL_REQUEST),
        )


def test_plan_rejects_undeclared_additional_suite() -> None:
    with pytest.raises(PlanningError, match="not declared"):
        compile_execution_plan(
            repository="setnessconsulting/web-example",
            sha="c" * 40,
            profile=_profile(),
            manifest=_manifest(),
            trust=ExecutionTrustClass.PR_UNTRUSTED,
            policy_version="1",
            context=PlanningContext(event=ExecutionEvent.PULL_REQUEST),
            additional_suite_ids=frozenset({"secret-shell"}),
        )


def test_plan_requires_exact_sha() -> None:
    with pytest.raises(PlanningError, match="full exact"):
        compile_execution_plan(
            repository="setnessconsulting/web-example",
            sha="abcdef1",
            profile=_profile(),
            manifest=_manifest(),
            trust=ExecutionTrustClass.PR_UNTRUSTED,
            policy_version="1",
            context=PlanningContext(event=ExecutionEvent.PULL_REQUEST),
        )
