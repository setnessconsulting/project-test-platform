"""QualityReceipt creation, validation, and bounded replay protection."""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from typing import Any

from test_platform.canonical import semantic_hash
from test_platform.contracts import (
    EvidenceClass,
    EvidenceReference,
    ExecutionPlan,
    ExecutionTrustClass,
    ProfileBinding,
    QualityReceipt,
    QualityResult,
    ToolVersion,
)


class ReceiptError(ValueError):
    """Raised when executor evidence does not match the approved plan."""


def _receipt_identity_payload(
    *,
    plan_id: str,
    repository: str,
    sha: str,
    profile: ProfileBinding,
    suite_id: str,
    executor: str,
    trust: ExecutionTrustClass,
    result: QualityResult,
    passed_tests: int,
    failed_tests: int,
    skipped_tests: int,
    duration_seconds: float,
    evidence: tuple[EvidenceReference, ...],
    tool_versions: tuple[ToolVersion, ...],
) -> dict[str, Any]:
    """Return the exact semantic content bound into a receipt identity.

    Build and validation share this single definition, so a receipt can never
    carry an identity that does not match its own content.
    """
    return {
        "plan_id": plan_id,
        "repository": repository,
        "sha": sha,
        "profile": profile.model_dump(mode="json"),
        "suite_id": suite_id,
        "executor": executor,
        "trust": trust.value,
        "result": result.value,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "skipped_tests": skipped_tests,
        "duration_seconds": duration_seconds,
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "tool_versions": [item.model_dump(mode="json") for item in tool_versions],
    }


def _expected_receipt_id(receipt: QualityReceipt) -> str:
    """Recompute a receipt's semantic identity from its own content."""
    return "receipt:" + semantic_hash(
        _receipt_identity_payload(
            plan_id=receipt.plan_id,
            repository=receipt.repository,
            sha=receipt.sha,
            profile=receipt.profile,
            suite_id=receipt.suite_id,
            executor=receipt.executor,
            trust=receipt.trust,
            result=receipt.result,
            passed_tests=receipt.passed_tests,
            failed_tests=receipt.failed_tests,
            skipped_tests=receipt.skipped_tests,
            duration_seconds=receipt.duration_seconds,
            evidence=receipt.evidence,
            tool_versions=receipt.tool_versions,
        )
    )[:24]


def build_quality_receipt(
    *,
    plan: ExecutionPlan,
    suite_id: str,
    executor: str,
    result: QualityResult,
    passed_tests: int,
    failed_tests: int,
    skipped_tests: int,
    duration_seconds: float,
    evidence: tuple[EvidenceReference, ...],
    tool_versions: tuple[ToolVersion, ...],
    generated_at: datetime,
) -> QualityReceipt:
    """Build a semantic-ID receipt after checking plan-bound invariants."""
    suites = {suite.suite_id: suite for suite in plan.suites}
    suite = suites.get(suite_id)
    if suite is None:
        raise ReceiptError(f"suite {suite_id} is not present in execution plan")
    if not executor.strip():
        raise ReceiptError("executor identity is required")
    if min(passed_tests, failed_tests, skipped_tests) < 0:
        raise ReceiptError("test counts cannot be negative")
    if duration_seconds < 0:
        raise ReceiptError("receipt duration cannot be negative")
    if result is QualityResult.PASS and failed_tests:
        raise ReceiptError("PASS receipt cannot report failed tests")

    live_evidence = tuple(item for item in evidence if item.live)
    if live_evidence and not any(
        item.evidence_class is EvidenceClass.LIVE
        for item in live_evidence
    ):
        raise ReceiptError("live evidence must use the live-qualification evidence class")

    payload = _receipt_identity_payload(
        plan_id=plan.plan_id,
        repository=plan.repository,
        sha=plan.sha,
        profile=plan.profile,
        suite_id=suite_id,
        executor=executor,
        trust=plan.trust,
        result=result,
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        skipped_tests=skipped_tests,
        duration_seconds=duration_seconds,
        evidence=evidence,
        tool_versions=tool_versions,
    )
    return QualityReceipt(
        receipt_id=f"receipt:{semantic_hash(payload)[:24]}",
        plan_id=plan.plan_id,
        repository=plan.repository,
        sha=plan.sha,
        profile=plan.profile,
        suite_id=suite_id,
        executor=executor,
        trust=plan.trust,
        result=result,
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        skipped_tests=skipped_tests,
        duration_seconds=duration_seconds,
        evidence=evidence,
        tool_versions=tool_versions,
        generated_at=generated_at,
    )


def validate_quality_receipt(
    plan: ExecutionPlan,
    receipt: QualityReceipt,
    *,
    seen_receipt_ids: Collection[str] = (),
) -> None:
    """Fail closed on forged identity, plan mismatch, invalid live evidence, or replay."""
    if receipt.receipt_id in seen_receipt_ids:
        raise ReceiptError(f"receipt replay detected: {receipt.receipt_id}")
    expected_id = _expected_receipt_id(receipt)
    if receipt.receipt_id != expected_id:
        raise ReceiptError(
            "receipt identity does not match its own semantic content; "
            "a receipt cannot carry a forged identifier"
        )
    if receipt.plan_id != plan.plan_id:
        raise ReceiptError("receipt plan ID does not match execution plan")
    if receipt.repository != plan.repository or receipt.sha != plan.sha:
        raise ReceiptError("receipt repository/SHA does not match execution plan")
    if receipt.profile != plan.profile:
        raise ReceiptError("receipt profile does not match execution plan")
    if receipt.trust != plan.trust:
        raise ReceiptError("receipt trust class does not match execution plan")
    if receipt.suite_id not in {suite.suite_id for suite in plan.suites}:
        raise ReceiptError("receipt suite is not present in execution plan")
    suite = next(item for item in plan.suites if item.suite_id == receipt.suite_id)
    if receipt.result is QualityResult.PASS and receipt.failed_tests:
        raise ReceiptError("PASS receipt reports failed tests")

    for evidence in receipt.evidence:
        if evidence.live and evidence.evidence_class is not EvidenceClass.LIVE:
            raise ReceiptError(
                "live evidence must use the live-qualification evidence class"
            )
        if evidence.live and plan.trust.value != "live-qualification":
            raise ReceiptError(
                "non-live execution plan cannot produce live qualification evidence"
            )

    # An evidence class the suite never declared is a trust widening attempt:
    # a unit suite cannot rest a receipt on end-to-end or live-qualification
    # evidence. A declared class is still not proof that the class was met.
    if suite.evidence_classes:
        undeclared = {
            item.evidence_class
            for item in receipt.evidence
            if item.evidence_class not in suite.evidence_classes
        }
        if undeclared:
            raise ReceiptError(
                "receipt cites evidence classes its suite does not declare: "
                + ", ".join(sorted(item.value for item in undeclared))
            )
