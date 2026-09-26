"""Deterministic repository quality-policy evaluation and exact-scope waiver handling."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from test_platform.canonical import semantic_hash
from test_platform.contracts import (
    EvidenceState,
    GapFinding,
    ProfileBinding,
    QualityAssessment,
    QualityProfile,
    QualityResult,
    RequirementLevel,
    TestValueFinding,
    Waiver,
)


class QualityEvaluationError(ValueError):
    """Raised when evaluation inputs attempt to widen policy or waiver scope."""


def exact_waiver_scope(repository: str, profile: ProfileBinding) -> str:
    """Return the only accepted V1 repository/profile waiver scope."""
    return f"repo:{repository}@profile:{profile.profile_id}:{profile.version}"


def _usable_waiver(
    waiver: Waiver,
    *,
    rule_id: str,
    expected_scope: str,
    now: datetime,
) -> bool:
    if "*" in waiver.scope:
        raise QualityEvaluationError("wildcard waiver scopes are prohibited")
    if waiver.rule_id != rule_id or waiver.scope != expected_scope:
        return False
    return waiver.expires_at is None or waiver.expires_at > now


def _blocking_gap_result(gaps: tuple[GapFinding, ...]) -> QualityResult | None:
    states = {item.state for item in gaps}
    if EvidenceState.NOT_EVALUABLE in states or EvidenceState.STALE in states:
        return QualityResult.NOT_EVALUABLE
    if EvidenceState.MISSING in states:
        return QualityResult.FAIL
    return None


def evaluate_quality(
    *,
    repository: str,
    sha: str,
    profile: QualityProfile,
    rule_states: Mapping[str, EvidenceState],
    behavior_gaps: tuple[GapFinding, ...] = (),
    test_value_findings: tuple[TestValueFinding, ...] = (),
    waivers: tuple[Waiver, ...] = (),
    applicable_conditional_rules: frozenset[str] = frozenset(),
    blocked_reasons: tuple[str, ...] = (),
    now: datetime,
) -> QualityAssessment:
    """Evaluate deterministic quality state without an opaque score or LLM judgment."""
    binding = ProfileBinding(profile_id=profile.profile_id, version=profile.version)
    expected_scope = exact_waiver_scope(repository, binding)
    applied_waivers: set[str] = set()
    synthetic_gaps: list[GapFinding] = list(behavior_gaps)

    result = QualityResult.BLOCKED if blocked_reasons else QualityResult.PASS

    for requirement in profile.requirements:
        if requirement.level in {
            RequirementLevel.INFORMATIONAL,
            RequirementLevel.NOT_APPLICABLE,
        }:
            continue
        if (
            requirement.level is RequirementLevel.CONDITIONAL
            and requirement.rule_id not in applicable_conditional_rules
        ):
            continue

        state = rule_states.get(requirement.rule_id, EvidenceState.NOT_EVALUABLE)
        if state is EvidenceState.PROVEN:
            continue
        if state is EvidenceState.NOT_APPLICABLE:
            state = EvidenceState.NOT_EVALUABLE

        matching = tuple(
            waiver
            for waiver in waivers
            if _usable_waiver(
                waiver,
                rule_id=requirement.rule_id,
                expected_scope=expected_scope,
                now=now,
            )
        )

        can_waive_missing = (
            state is EvidenceState.MISSING
            and not requirement.non_waivable
            and bool(matching)
        )
        if can_waive_missing:
            applied_waivers.update(item.waiver_id for item in matching)
            continue

        reason = (
            f"profile rule {requirement.rule_id} is {state.value}; "
            "required quality evidence is not satisfied"
        )
        finding_payload = {
            "rule_id": requirement.rule_id,
            "state": state.value,
            "repository": repository,
            "profile": binding.model_dump(mode="json"),
        }
        synthetic_gaps.append(
            GapFinding(
                finding_id=f"rule-gap:{semantic_hash(finding_payload)[:24]}",
                behavior_id=f"profile-rule:{requirement.rule_id}",
                state=state,
                reasons=(reason,),
            )
        )

    gaps = tuple(sorted(synthetic_gaps, key=lambda item: item.behavior_id))

    if result is not QualityResult.BLOCKED:
        gap_result = _blocking_gap_result(gaps)
        if gap_result is not None:
            result = gap_result

    assessment_payload = {
        "repository": repository,
        "sha": sha,
        "profile": binding.model_dump(mode="json"),
        "result": result.value,
        "gaps": [item.model_dump(mode="json") for item in gaps],
        "waiver_ids": sorted(applied_waivers),
    }

    return QualityAssessment(
        assessment_id=f"assessment:{semantic_hash(assessment_payload)[:24]}",
        repository=repository,
        sha=sha,
        profile=binding,
        result=result,
        gaps=gaps,
        test_value_findings=tuple(
            sorted(test_value_findings, key=lambda item: item.test_id)
        ),
        waiver_ids=tuple(sorted(applied_waivers)),
    )
