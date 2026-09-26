"""Deterministic advisory test-value analysis."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from test_platform.canonical import semantic_hash
from test_platform.contracts import (
    TestCaseObservation,
    TestInventory,
    TestValueClassification,
    TestValueFinding,
)


@dataclass(frozen=True)
class TestValueSignals:
    """Explicit evidence used to classify one test.

    These signals are produced by deterministic repository/history analyses or reviewed
    declarations. They are never inferred from a test name by this module.
    """

    unique_behavior_protection: bool = False
    critical_behavior_protection: bool = False
    security_boundary_protection: bool = False
    historical_regression_protection: bool = False
    duplicate_evidence_ids: tuple[str, ...] = ()
    implementation_coupled: bool = False
    trivial_assertion: bool = False
    flaky: bool = False
    obsolete: bool = False
    execution_cost_seconds: float | None = None
    evidence_ids: tuple[str, ...] = ()


def _finding(
    test: TestCaseObservation,
    classification: TestValueClassification,
    reasons: tuple[str, ...],
    evidence_ids: tuple[str, ...],
) -> TestValueFinding:
    payload = {
        "test_id": test.test_id,
        "classification": classification.value,
        "reasons": sorted(reasons),
        "evidence_ids": sorted(set(evidence_ids)),
    }
    return TestValueFinding(
        finding_id=f"test-value:{semantic_hash(payload)[:24]}",
        test_id=test.test_id,
        classification=classification,
        reasons=tuple(sorted(reasons)),
        evidence_ids=tuple(sorted(set(evidence_ids))),
    )


def classify_test_value(
    test: TestCaseObservation,
    signals: TestValueSignals | None,
) -> TestValueFinding:
    """Classify one test from explicit evidence, preferring protection over cleanup signals."""
    if signals is None:
        return _finding(
            test,
            TestValueClassification.UNKNOWN,
            ("no deterministic value signals are available",),
            (),
        )

    evidence_ids = tuple(sorted(set(signals.evidence_ids + signals.duplicate_evidence_ids)))

    if signals.obsolete:
        return _finding(
            test,
            TestValueClassification.OBSOLETE,
            ("reviewed evidence marks the protected behavior or test contract obsolete",),
            evidence_ids,
        )

    required_reasons: list[str] = []
    if signals.unique_behavior_protection:
        required_reasons.append("provides unique declared-behavior protection")
    if signals.critical_behavior_protection:
        required_reasons.append("protects a critical declared behavior or journey")
    if signals.security_boundary_protection:
        required_reasons.append("protects a security or authorization boundary")
    if signals.historical_regression_protection:
        required_reasons.append("protects an observed historical regression")

    if required_reasons:
        if signals.flaky:
            required_reasons.append(
                "is flaky and needs repair, but flakiness does not erase required protection"
            )
        return _finding(
            test,
            TestValueClassification.REQUIRED,
            tuple(required_reasons),
            evidence_ids,
        )

    if signals.flaky:
        return _finding(
            test,
            TestValueClassification.FLAKY,
            ("observed outcomes vary for an equivalent test context",),
            evidence_ids,
        )

    if signals.implementation_coupled:
        return _finding(
            test,
            TestValueClassification.IMPLEMENTATION_COUPLED,
            ("reviewed evidence shows implementation-detail coupling",),
            evidence_ids,
        )

    if signals.trivial_assertion and not test.behavior_ids:
        return _finding(
            test,
            TestValueClassification.TRIVIAL,
            ("test has no declared behavior link and reviewed evidence marks its assertion trivial",),
            evidence_ids,
        )

    if signals.duplicate_evidence_ids and not signals.unique_behavior_protection:
        return _finding(
            test,
            TestValueClassification.POSSIBLY_REDUNDANT,
            ("other evidence protects the same declared behavior without a distinct failure mode",),
            evidence_ids,
        )

    if test.behavior_ids:
        reasons = ["has explicit declared-behavior traceability"]
        if signals.execution_cost_seconds is not None:
            reasons.append(
                f"observed execution cost is {signals.execution_cost_seconds:g} seconds"
            )
        return _finding(
            test,
            TestValueClassification.USEFUL,
            tuple(reasons),
            evidence_ids,
        )

    return _finding(
        test,
        TestValueClassification.UNKNOWN,
        ("insufficient deterministic evidence to classify test value",),
        evidence_ids,
    )


def analyze_test_values(
    inventory: TestInventory,
    signals_by_test: Mapping[str, TestValueSignals],
) -> tuple[TestValueFinding, ...]:
    """Return deterministic advisory findings for every inventoried test."""
    findings = [
        classify_test_value(test, signals_by_test.get(test.test_id))
        for test in inventory.tests
    ]
    return tuple(sorted(findings, key=lambda item: item.test_id))
