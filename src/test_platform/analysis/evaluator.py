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


def exact_waiver_scope(repository: str, profile: ProfileBinding, sha: str) -> str:
    """Return the only accepted V1 repository/profile/revision waiver scope.

    The revision is part of the scope so a waiver granted against one commit
    cannot silently carry over to a later one.
    """
    return f"repo:{repository}@profile:{profile.profile_id}:{profile.version}@sha:{sha}"


def _validate_waiver_set(waivers: tuple[Waiver, ...]) -> None:
    """Reject a hostile waiver file deterministically before any evaluation.

    Wildcard scopes and duplicate waiver IDs are refused up front. Doing this
    once, before the per-rule loop, means an invalid waiver cannot abort
    evaluation partway through or be masked by an unrelated proven rule.
    """
    seen: set[str] = set()
    for waiver in waivers:
        if "*" in waiver.scope:
            raise QualityEvaluationError("wildcard waiver scopes are prohibited")
        if waiver.waiver_id in seen:
            raise QualityEvaluationError("duplicate waiver identifiers are prohibited")
        seen.add(waiver.waiver_id)


def _waiver_rejection(
    waiver: Waiver,
    *,
    rule_id: str,
    expected_scope: str,
    now: datetime,
) -> str | None:
    """Return why a waiver does not apply, or None when it is usable."""
    if waiver.rule_id != rule_id or waiver.scope != expected_scope:
        return "out-of-scope"
    if waiver.expires_at is not None and waiver.expires_at <= now:
        return "expired"
    return None


def _usable_waiver(
    waiver: Waiver,
    *,
    rule_id: str,
    expected_scope: str,
    now: datetime,
) -> bool:
    return _waiver_rejection(
        waiver,
        rule_id=rule_id,
        expected_scope=expected_scope,
        now=now,
    ) is None


def _blocking_gap_result(gaps: tuple[GapFinding, ...]) -> QualityResult | None:
    """Derive the worst aggregate result from any non-proven gap.

    Only ``PROVEN`` is non-blocking. Every other evidence state — including
    ``NOT_APPLICABLE``, which a repository could otherwise assert for any
    required evidence class to make a gap disappear — degrades the aggregate
    result. Nothing here can produce ``PASS``.
    """
    states = {item.state for item in gaps}
    if states - {EvidenceState.PROVEN, EvidenceState.MISSING}:
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
    behavior_gaps_evaluated: bool = True,
    test_value_findings: tuple[TestValueFinding, ...] = (),
    waivers: tuple[Waiver, ...] = (),
    applicable_conditional_rules: frozenset[str] = frozenset(),
    blocked_reasons: tuple[str, ...] = (),
    now: datetime,
) -> QualityAssessment:
    """Evaluate deterministic quality state without an opaque score or LLM judgment."""
    binding = ProfileBinding(profile_id=profile.profile_id, version=profile.version)
    expected_scope = exact_waiver_scope(repository, binding, sha)
    _validate_waiver_set(waivers)
    applied_waivers: set[str] = set()
    rejected_waivers: list[str] = []
    synthetic_gaps: list[GapFinding] = list(behavior_gaps)

    result = QualityResult.BLOCKED if blocked_reasons else QualityResult.PASS

    if not behavior_gaps_evaluated:
        # Behavior-level analysis was never run. An unverified repository must
        # never aggregate to PASS; it is explicitly not evaluable.
        result = (
            QualityResult.BLOCKED
            if result is QualityResult.BLOCKED
            else QualityResult.NOT_EVALUABLE
        )
        blocked_reasons = (*blocked_reasons, "behavior gap analysis was not evaluated")

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

        matching: list[Waiver] = []
        for waiver in waivers:
            rejection = _waiver_rejection(
                waiver,
                rule_id=requirement.rule_id,
                expected_scope=expected_scope,
                now=now,
            )
            if rejection is None:
                matching.append(waiver)
            else:
                rejected_waivers.append(f"{waiver.waiver_id}:{rejection}")

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
        relevant_rejections = sorted(
            item for item in rejected_waivers if not item.endswith(":out-of-scope")
        )
        reasons = [reason]
        if relevant_rejections:
            reasons.append(
                "waivers presented for this rule were not usable: "
                + ", ".join(relevant_rejections)
            )
        synthetic_gaps.append(
            GapFinding(
                finding_id=f"rule-gap:{semantic_hash(finding_payload)[:24]}",
                behavior_id=f"profile-rule:{requirement.rule_id}",
                state=state,
                reasons=tuple(reasons),
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
