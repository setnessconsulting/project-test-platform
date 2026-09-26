from __future__ import annotations

from test_platform.analysis import TestValueSignals, analyze_test_values, classify_test_value
from test_platform.contracts import (
    EvidenceClass,
    TestCaseObservation,
    TestInventory,
    TestValueClassification,
)


def _test(*, behavior_ids: tuple[str, ...] = ()) -> TestCaseObservation:
    return TestCaseObservation(
        test_id="pytest:tests/test_policy.py",
        framework="pytest",
        path="tests/test_policy.py",
        behavior_ids=behavior_ids,
        evidence_class=EvidenceClass.DETERMINISTIC,
    )


def test_required_protection_outranks_flake_cleanup_signal() -> None:
    finding = classify_test_value(
        _test(behavior_ids=("policy.target-binding",)),
        TestValueSignals(
            critical_behavior_protection=True,
            flaky=True,
            evidence_ids=("history-1",),
        ),
    )

    assert finding.classification is TestValueClassification.REQUIRED
    assert "flaky" in " ".join(finding.reasons)


def test_duplicate_without_unique_failure_mode_is_only_possible_redundancy() -> None:
    finding = classify_test_value(
        _test(behavior_ids=("behavior.example",)),
        TestValueSignals(duplicate_evidence_ids=("test:other",)),
    )

    assert finding.classification is TestValueClassification.POSSIBLY_REDUNDANT
    assert finding.evidence_ids == ("test:other",)


def test_no_signals_stays_unknown_instead_of_guessing_from_name() -> None:
    finding = classify_test_value(_test(), None)
    assert finding.classification is TestValueClassification.UNKNOWN


def test_behavior_link_defaults_to_useful_when_no_stronger_signal_exists() -> None:
    finding = classify_test_value(
        _test(behavior_ids=("behavior.example",)),
        TestValueSignals(execution_cost_seconds=42.0),
    )

    assert finding.classification is TestValueClassification.USEFUL
    assert "42" in " ".join(finding.reasons)


def test_inventory_analysis_is_deterministic_and_complete() -> None:
    inventory = TestInventory(
        repository="setnessconsulting/example",
        sha="abcdef1234567",
        tests=(
            _test(behavior_ids=("behavior.example",)),
            TestCaseObservation(
                test_id="playwright:e2e/main.spec.ts",
                framework="playwright",
                path="e2e/main.spec.ts",
                evidence_class=EvidenceClass.E2E,
            ),
        ),
    )

    first = analyze_test_values(
        inventory,
        {
            "pytest:tests/test_policy.py": TestValueSignals(
                unique_behavior_protection=True
            )
        },
    )
    second = analyze_test_values(
        inventory,
        {
            "pytest:tests/test_policy.py": TestValueSignals(
                unique_behavior_protection=True
            )
        },
    )

    assert first == second
    assert len(first) == 2
    assert first[0].finding_id == second[0].finding_id
