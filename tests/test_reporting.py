from __future__ import annotations

from datetime import UTC, datetime

import pytest

from test_platform.contracts import (
    Behavior,
    BehaviorDocument,
    CriticalJourney,
    Criticality,
    EvidenceClass,
    EvidenceState,
    GapFinding,
    ProfileBinding,
    QualityAssessment,
    QualityResult,
)
from test_platform.reporting import (
    MAX_OUTPUT_BYTES,
    ReportingError,
    build_quality_export,
    public_safe_value,
    serialize_json,
)


def _behaviors() -> BehaviorDocument:
    return BehaviorDocument(
        behaviors=(
            Behavior(
                behavior_id="auth.sign-in",
                description="Authorized user signs in.",
                criticality=Criticality.CRITICAL,
                required_evidence=(EvidenceClass.INTEGRATION,),
            ),
        ),
        critical_journeys=(
            CriticalJourney(
                journey_id="login",
                description="User completes login.",
                behavior_ids=("auth.sign-in",),
            ),
        ),
    )


def _assessment() -> QualityAssessment:
    return QualityAssessment(
        assessment_id="assessment:example",
        repository="setnessconsulting/example",
        sha="a" * 40,
        profile=ProfileBinding(
            profile_id="web-application-v1",
            version="1.0.0",
        ),
        result=QualityResult.PASS,
        gaps=(
            GapFinding(
                finding_id="gap:behavior",
                behavior_id="auth.sign-in",
                state=EvidenceState.PROVEN,
                reasons=("current evidence proven",),
                evidence_ids=("evidence-1",),
            ),
            GapFinding(
                finding_id="gap:journey",
                behavior_id="journey:login",
                state=EvidenceState.PROVEN,
                reasons=("current journey proven",),
                evidence_ids=("evidence-2",),
            ),
        ),
    )


def test_public_safe_value_redacts_paths_and_sensitive_fields() -> None:
    value = {
        "workspace": r"C:\Users\Example\repo",
        "artifact": "/home/example/private/report.json",
        "token_hint": "should-not-leak",
        "relative": "tests/test_example.py",
    }

    safe = public_safe_value(value)

    assert safe["workspace"] == "<redacted-path>"
    assert safe["artifact"] == "<redacted-path>"
    assert safe["token_hint"] == "<redacted>"
    assert safe["relative"] == "tests/test_example.py"


def test_quality_export_requires_complete_behavior_and_journey_state() -> None:
    first = build_quality_export(
        _assessment(),
        _behaviors(),
        receipt_ids=("receipt-2", "receipt-1", "receipt-1"),
        generated_at=datetime(2026, 9, 25, tzinfo=UTC),
    )
    second = build_quality_export(
        _assessment(),
        _behaviors(),
        receipt_ids=("receipt-1", "receipt-2"),
        generated_at=datetime(2026, 9, 26, tzinfo=UTC),
    )

    assert first.export_id == second.export_id
    assert first.required_behaviors == 1
    assert first.proven_behaviors == 1
    assert first.critical_journeys_required == 1
    assert first.critical_journeys_proven == 1
    assert first.receipt_ids == ("receipt-1", "receipt-2")


def test_quality_export_fails_closed_on_partial_findings() -> None:
    assessment = _assessment().model_copy(
        update={"gaps": (_assessment().gaps[0],)}
    )

    with pytest.raises(ReportingError, match="complete behavior/journey"):
        build_quality_export(
            assessment,
            _behaviors(),
            receipt_ids=(),
            generated_at=datetime(2026, 9, 25, tzinfo=UTC),
        )


def test_json_output_is_bounded() -> None:
    oversized = {"payload": "x" * (MAX_OUTPUT_BYTES + 1)}
    with pytest.raises(ReportingError, match="maximum size"):
        serialize_json(oversized)
