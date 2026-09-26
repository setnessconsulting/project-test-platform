"""Deterministic behavior and critical-journey evidence-gap analysis."""

from __future__ import annotations

from dataclasses import dataclass

from test_platform.canonical import semantic_hash
from test_platform.contracts import (
    Behavior,
    BehaviorDocument,
    EvidenceClass,
    EvidenceState,
    GapFinding,
    ProfileBinding,
)


@dataclass(frozen=True)
class BehaviorEvidenceObservation:
    """One bounded piece of evidence offered for a behavior or journey."""

    evidence_id: str
    subject_id: str
    evidence_class: EvidenceClass
    state: EvidenceState
    sha: str
    profile: ProfileBinding


_STATE_PRIORITY = {
    EvidenceState.MISSING: 4,
    EvidenceState.NOT_EVALUABLE: 3,
    EvidenceState.STALE: 2,
    EvidenceState.NOT_APPLICABLE: 1,
    EvidenceState.PROVEN: 0,
}


def _stable_finding(
    subject_id: str,
    state: EvidenceState,
    reasons: tuple[str, ...],
    evidence_ids: tuple[str, ...],
) -> GapFinding:
    payload = {
        "subject_id": subject_id,
        "state": state.value,
        "reasons": sorted(reasons),
        "evidence_ids": sorted(set(evidence_ids)),
    }
    return GapFinding(
        finding_id=f"gap:{semantic_hash(payload)[:24]}",
        behavior_id=subject_id,
        state=state,
        reasons=tuple(sorted(reasons)),
        evidence_ids=tuple(sorted(set(evidence_ids))),
    )


def _effective_state(
    observation: BehaviorEvidenceObservation,
    *,
    sha: str,
    profile: ProfileBinding,
) -> EvidenceState:
    if observation.sha != sha or observation.profile != profile:
        return EvidenceState.STALE
    return observation.state


def _evaluate_required_classes(
    *,
    subject_id: str,
    required: tuple[EvidenceClass, ...],
    observations: tuple[BehaviorEvidenceObservation, ...],
    sha: str,
    profile: ProfileBinding,
) -> GapFinding:
    reasons: list[str] = []
    evidence_ids: set[str] = set()
    class_states: list[EvidenceState] = []

    for evidence_class in required:
        candidates = tuple(
            item
            for item in observations
            if item.subject_id == subject_id and item.evidence_class is evidence_class
        )
        if not candidates:
            class_states.append(EvidenceState.MISSING)
            reasons.append(f"missing required {evidence_class.value} evidence")
            continue

        effective = [
            (_effective_state(item, sha=sha, profile=profile), item)
            for item in candidates
        ]
        for _, item in effective:
            evidence_ids.add(item.evidence_id)

        if any(state is EvidenceState.PROVEN for state, _ in effective):
            class_states.append(EvidenceState.PROVEN)
            continue
        if any(state is EvidenceState.NOT_EVALUABLE for state, _ in effective):
            class_states.append(EvidenceState.NOT_EVALUABLE)
            reasons.append(f"{evidence_class.value} evidence is not evaluable")
            continue
        if any(state is EvidenceState.STALE for state, _ in effective):
            class_states.append(EvidenceState.STALE)
            reasons.append(f"{evidence_class.value} evidence is stale or bound to another revision")
            continue
        if all(state is EvidenceState.NOT_APPLICABLE for state, _ in effective):
            class_states.append(EvidenceState.NOT_APPLICABLE)
            reasons.append(f"{evidence_class.value} evidence is explicitly not applicable")
            continue

        class_states.append(EvidenceState.MISSING)
        reasons.append(f"{evidence_class.value} evidence does not prove the requirement")

    if not required or all(item is EvidenceState.PROVEN for item in class_states):
        state = EvidenceState.PROVEN
    else:
        non_proven = [item for item in class_states if item is not EvidenceState.PROVEN]
        state = max(non_proven, key=lambda item: _STATE_PRIORITY[item])

    if state is EvidenceState.PROVEN:
        reasons = ["all required evidence classes are proven for the current revision"]

    return _stable_finding(
        subject_id,
        state,
        tuple(reasons),
        tuple(evidence_ids),
    )


def _evaluate_behavior(
    behavior: Behavior,
    observations: tuple[BehaviorEvidenceObservation, ...],
    *,
    sha: str,
    profile: ProfileBinding,
) -> GapFinding:
    return _evaluate_required_classes(
        subject_id=behavior.behavior_id,
        required=behavior.required_evidence,
        observations=observations,
        sha=sha,
        profile=profile,
    )


def analyze_behavior_gaps(
    document: BehaviorDocument,
    observations: tuple[BehaviorEvidenceObservation, ...],
    *,
    sha: str,
    profile: ProfileBinding,
) -> tuple[GapFinding, ...]:
    """Evaluate declared behaviors and critical journeys against exact-revision evidence."""
    behavior_findings = {
        behavior.behavior_id: _evaluate_behavior(
            behavior,
            observations,
            sha=sha,
            profile=profile,
        )
        for behavior in document.behaviors
    }

    findings: list[GapFinding] = list(behavior_findings.values())

    for journey in document.critical_journeys:
        subject_id = f"journey:{journey.journey_id}"
        journey_evidence = _evaluate_required_classes(
            subject_id=subject_id,
            required=journey.required_evidence,
            observations=observations,
            sha=sha,
            profile=profile,
        )
        constituent = [behavior_findings[item] for item in journey.behavior_ids]

        if any(item.state is not EvidenceState.PROVEN for item in constituent):
            worst = max(
                (item.state for item in constituent if item.state is not EvidenceState.PROVEN),
                key=lambda item: _STATE_PRIORITY[item],
            )
            evidence_ids = tuple(
                sorted(
                    set(journey_evidence.evidence_ids).union(
                        *(set(item.evidence_ids) for item in constituent)
                    )
                )
            )
            reasons = (
                "one or more constituent behaviors are not proven for the current revision",
            )
            findings.append(_stable_finding(subject_id, worst, reasons, evidence_ids))
        else:
            findings.append(journey_evidence)

    return tuple(sorted(findings, key=lambda item: item.behavior_id))
