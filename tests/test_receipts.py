from __future__ import annotations

from datetime import UTC, datetime

import pytest

from test_platform.contracts import (
    EvidenceClass,
    EvidenceReference,
    ExecutionPlan,
    ExecutionTrustClass,
    ProfileBinding,
    QualityResult,
    SuiteDefinition,
)
from test_platform.evidence.receipts import (
    ReceiptError,
    build_quality_receipt,
    validate_quality_receipt,
)

NOW = datetime(2026, 9, 25, tzinfo=UTC)


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        plan_id="plan:example",
        repository="setnessconsulting/example",
        sha="a" * 40,
        profile=ProfileBinding(profile_id="web-application-v1", version="1.0.0"),
        trust=ExecutionTrustClass.PR_UNTRUSTED,
        policy_version="1",
        suites=(
            SuiteDefinition(
                suite_id="standard",
                entrypoint="test:standard",
                trust=ExecutionTrustClass.PR_UNTRUSTED,
                evidence_classes=(EvidenceClass.DETERMINISTIC,),
            ),
        ),
    )


def test_receipt_is_plan_bound_and_semantically_stable() -> None:
    plan = _plan()
    first = build_quality_receipt(
        plan=plan,
        suite_id="standard",
        executor="jenkins",
        result=QualityResult.PASS,
        passed_tests=10,
        failed_tests=0,
        skipped_tests=1,
        duration_seconds=4.2,
        evidence=(),
        tool_versions=(),
        generated_at=NOW,
    )
    second = build_quality_receipt(
        plan=plan,
        suite_id="standard",
        executor="jenkins",
        result=QualityResult.PASS,
        passed_tests=10,
        failed_tests=0,
        skipped_tests=1,
        duration_seconds=4.2,
        evidence=(),
        tool_versions=(),
        generated_at=NOW.replace(hour=1),
    )

    assert first.receipt_id == second.receipt_id
    validate_quality_receipt(plan, first)


def test_receipt_replay_is_explicitly_rejected() -> None:
    plan = _plan()
    receipt = build_quality_receipt(
        plan=plan,
        suite_id="standard",
        executor="jenkins",
        result=QualityResult.PASS,
        passed_tests=1,
        failed_tests=0,
        skipped_tests=0,
        duration_seconds=1.0,
        evidence=(),
        tool_versions=(),
        generated_at=NOW,
    )

    with pytest.raises(ReceiptError, match="replay"):
        validate_quality_receipt(
            plan,
            receipt,
            seen_receipt_ids={receipt.receipt_id},
        )


def test_non_live_plan_cannot_claim_live_evidence() -> None:
    plan = _plan()
    receipt = build_quality_receipt(
        plan=plan,
        suite_id="standard",
        executor="jenkins",
        result=QualityResult.PASS,
        passed_tests=1,
        failed_tests=0,
        skipped_tests=0,
        duration_seconds=1.0,
        evidence=(
            EvidenceReference(
                evidence_id="live-1",
                evidence_class=EvidenceClass.LIVE,
                live=True,
                source="provider",
            ),
        ),
        tool_versions=(),
        generated_at=NOW,
    )

    with pytest.raises(ReceiptError, match="non-live"):
        validate_quality_receipt(plan, receipt)


def test_pass_receipt_cannot_hide_failed_tests() -> None:
    with pytest.raises(ReceiptError, match="PASS"):
        build_quality_receipt(
            plan=_plan(),
            suite_id="standard",
            executor="jenkins",
            result=QualityResult.PASS,
            passed_tests=1,
            failed_tests=1,
            skipped_tests=0,
            duration_seconds=1.0,
            evidence=(),
            tool_versions=(),
            generated_at=NOW,
        )
