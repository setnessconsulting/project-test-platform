from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from test_platform.canonical import semantic_hash
from test_platform.contracts import (
    Criticality,
    EvidenceClass,
    ExecutionPlan,
    ExecutionTrustClass,
    ProfileBinding,
    ProfileRequirement,
    QualityExport,
    QualityProfile,
    QualityReceipt,
    QualityResult,
    RepositoryManifest,
    RequirementLevel,
    SuiteDefinition,
    Waiver,
)
from test_platform.schema_registry import (
    SCHEMA_DIALECT,
    check_schema_bundle,
    expected_schema_bundle,
)


def _profile() -> QualityProfile:
    return QualityProfile(
        profile_id="browser-game-v1",
        version="1.0.0",
        requirements=(
            ProfileRequirement(
                rule_id="critical-journey-e2e",
                evidence_class=EvidenceClass.E2E,
                level=RequirementLevel.REQUIRED,
                non_waivable=True,
                description="Critical journeys require assembled E2E evidence.",
            ),
        ),
    )


def _manifest() -> RepositoryManifest:
    return RepositoryManifest(
        profile=ProfileBinding(profile_id="browser-game-v1", version="1.0.0"),
        behaviors_path="quality/behaviors.yaml",
        suites=(
            SuiteDefinition(
                suite_id="e2e",
                entrypoint="test:e2e",
                trust=ExecutionTrustClass.PR_UNTRUSTED,
                evidence_classes=(EvidenceClass.E2E,),
            ),
        ),
    )


def test_contract_models_round_trip_strictly() -> None:
    profile = _profile()
    manifest = _manifest()

    assert QualityProfile.model_validate(profile.model_dump(mode="json")) == profile
    assert RepositoryManifest.model_validate(manifest.model_dump(mode="json")) == manifest

    with pytest.raises(ValidationError):
        QualityProfile.model_validate(
            {
                **profile.model_dump(mode="json"),
                "unexpected": "must fail closed",
            }
        )


def test_generated_schema_validates_contract_payload() -> None:
    profile = _profile()
    bundle = expected_schema_bundle()
    schema = {
        "$schema": SCHEMA_DIALECT,
        "$ref": "#/$defs/QualityProfile",
        "$defs": bundle["$defs"],
    }

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(profile.model_dump(mode="json"))


def test_semantic_hash_ignores_receipt_generation_time_only() -> None:
    profile = ProfileBinding(profile_id="browser-game-v1", version="1.0.0")
    base = dict(
        receipt_id="receipt-1",
        plan_id="plan-1",
        repository="setnessconsulting/game-example",
        sha="abcdef1234567",
        profile=profile,
        suite_id="e2e",
        executor="jenkins",
        trust=ExecutionTrustClass.PR_UNTRUSTED,
        result=QualityResult.PASS,
    )
    first = QualityReceipt(generated_at=datetime(2026, 1, 1, tzinfo=UTC), **base)
    second = QualityReceipt(generated_at=datetime(2026, 1, 2, tzinfo=UTC), **base)

    assert semantic_hash(first.semantic_payload()) == semantic_hash(second.semantic_payload())


def test_quality_export_semantic_hash_ignores_generation_time_only() -> None:
    profile = ProfileBinding(profile_id="web-application-v1", version="1.0.0")
    base = dict(
        export_id="export-1",
        repository="setnessconsulting/web-example",
        sha="abcdef1234567",
        profile=profile,
        result=QualityResult.PASS,
        required_behaviors=4,
        proven_behaviors=4,
        not_evaluable_behaviors=0,
    )
    first = QualityExport(generated_at=datetime(2026, 1, 1, tzinfo=UTC), **base)
    second = QualityExport(generated_at=datetime(2026, 1, 2, tzinfo=UTC), **base)

    assert semantic_hash(first.semantic_payload()) == semantic_hash(second.semantic_payload())


def test_waiver_expiry_must_follow_creation() -> None:
    created = datetime(2026, 1, 1, tzinfo=UTC)

    with pytest.raises(ValidationError):
        Waiver(
            waiver_id="waiver-1",
            rule_id="rule-1",
            scope="repo:example",
            reason="temporary compatibility exception",
            owner_decision_ref="JIRA-1",
            created_at=created,
            expires_at=created - timedelta(seconds=1),
        )


def test_execution_plan_binds_sha_profile_policy_and_trust() -> None:
    plan = ExecutionPlan(
        plan_id="plan-1",
        repository="setnessconsulting/example",
        sha="abcdef1234567",
        profile=ProfileBinding(profile_id="python-control-plane-v1", version="1.0.0"),
        trust=ExecutionTrustClass.PR_UNTRUSTED,
        policy_version="1",
        suites=(),
    )

    assert plan.sha == "abcdef1234567"
    assert plan.trust is ExecutionTrustClass.PR_UNTRUSTED


def test_checked_in_schema_bundle_matches_models() -> None:
    assert check_schema_bundle(Path("schemas/v1/contracts.schema.json"))
