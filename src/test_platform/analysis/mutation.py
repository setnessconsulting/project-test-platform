"""Selective, profile-driven mutation and fault-injection evidence analysis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from test_platform.canonical import semantic_hash
from test_platform.contracts import (
    EvidenceState,
    GapFinding,
    QualityProfile,
    RequirementLevel,
)


class MutationTrialState(StrEnum):
    KILLED = "killed"
    SURVIVED = "survived"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass(frozen=True)
class MutationTrial:
    """One bounded mutation or injected-fault observation."""

    trial_id: str
    target_id: str
    state: MutationTrialState
    duration_seconds: float
    evidence_id: str | None = None


@dataclass(frozen=True)
class MutationLimits:
    """Hard cost bounds for selective mutation analysis."""

    max_trials: int = 250
    max_total_seconds: float = 1_800.0


class MutationAnalysisError(ValueError):
    """Raised when supplied mutation evidence violates configured safety bounds."""


def _finding(
    *,
    state: EvidenceState,
    reasons: tuple[str, ...],
    evidence_ids: tuple[str, ...],
) -> GapFinding:
    payload = {
        "subject": "profile:mutation-analysis",
        "state": state.value,
        "reasons": sorted(reasons),
        "evidence_ids": sorted(set(evidence_ids)),
    }
    return GapFinding(
        finding_id=f"mutation:{semantic_hash(payload)[:24]}",
        behavior_id="profile:mutation-analysis",
        state=state,
        reasons=tuple(sorted(reasons)),
        evidence_ids=tuple(sorted(set(evidence_ids))),
    )


def analyze_mutation_evidence(
    profile: QualityProfile,
    trials: tuple[MutationTrial, ...],
    *,
    limits: MutationLimits | None = None,
) -> GapFinding:
    """Evaluate bounded mutation evidence only when the profile makes it applicable."""
    limits = limits or MutationLimits()

    if len(trials) > limits.max_trials:
        raise MutationAnalysisError(
            f"mutation trial count {len(trials)} exceeds limit {limits.max_trials}"
        )
    if any(item.duration_seconds < 0 for item in trials):
        raise MutationAnalysisError("mutation duration cannot be negative")

    total_duration = sum(item.duration_seconds for item in trials)
    if total_duration > limits.max_total_seconds:
        raise MutationAnalysisError(
            f"mutation duration {total_duration:g}s exceeds limit "
            f"{limits.max_total_seconds:g}s"
        )

    if profile.mutation_analysis is RequirementLevel.NOT_APPLICABLE:
        if trials:
            return _finding(
                state=EvidenceState.NOT_APPLICABLE,
                reasons=(
                    "profile does not require mutation analysis; supplied trials are informational",
                ),
                evidence_ids=tuple(
                    item.evidence_id for item in trials if item.evidence_id is not None
                ),
            )
        return _finding(
            state=EvidenceState.NOT_APPLICABLE,
            reasons=("profile marks mutation analysis not applicable",),
            evidence_ids=(),
        )

    if not trials:
        state = (
            EvidenceState.MISSING
            if profile.mutation_analysis is RequirementLevel.REQUIRED
            else EvidenceState.NOT_EVALUABLE
        )
        return _finding(
            state=state,
            reasons=("applicable mutation analysis has no bounded trial evidence",),
            evidence_ids=(),
        )

    evidence_ids = tuple(
        item.evidence_id for item in trials if item.evidence_id is not None
    )
    if any(item.state in {MutationTrialState.TIMEOUT, MutationTrialState.ERROR} for item in trials):
        return _finding(
            state=EvidenceState.NOT_EVALUABLE,
            reasons=("one or more mutation trials timed out or errored",),
            evidence_ids=evidence_ids,
        )

    survived = tuple(sorted(item.trial_id for item in trials if item.state is MutationTrialState.SURVIVED))
    if survived:
        return _finding(
            state=EvidenceState.MISSING,
            reasons=(
                "surviving mutation/fault trials reveal an evidence gap: "
                + ", ".join(survived),
            ),
            evidence_ids=evidence_ids,
        )

    return _finding(
        state=EvidenceState.PROVEN,
        reasons=("all bounded applicable mutation/fault trials were detected",),
        evidence_ids=evidence_ids,
    )
