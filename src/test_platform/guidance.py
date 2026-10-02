"""Deterministic AI-agent testing guidance from canonical Test Platform facts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from test_platform.contracts import (
    BehaviorDocument,
    EvidenceClass,
    EvidenceState,
    GapFinding,
    ProfileBinding,
    QualityProfile,
    RepositoryManifest,
    TestInventory,
    exact_sha_field,
)


class GuidanceTest(BaseModel):
    """One existing test relevant to an affected behavior."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    test_id: str
    evidence_class: EvidenceClass
    behavior_ids: tuple[str, ...]


class GuidanceJourney(BaseModel):
    """One affected critical journey that must retain assembled evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    journey_id: str
    behavior_ids: tuple[str, ...]
    required_evidence: tuple[EvidenceClass, ...]


class AgentTestingGuidance(BaseModel):
    """Versioned consumer-neutral testing guidance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    repository: str = Field(min_length=1)
    sha: str = exact_sha_field()
    profile: ProfileBinding
    affected_behavior_ids: tuple[str, ...]
    required_evidence: tuple[EvidenceClass, ...]
    conditional_evidence: tuple[EvidenceClass, ...]
    relevant_tests: tuple[GuidanceTest, ...]
    relevant_evidence_ids: tuple[str, ...]
    relevant_gaps: tuple[GapFinding, ...]
    critical_journeys: tuple[GuidanceJourney, ...]
    suite_ids_to_verify: tuple[str, ...]
    new_test_needed: bool
    next_actions: tuple[str, ...]
    anti_patterns: tuple[str, ...]


class GuidanceError(ValueError):
    """Raised when trusted change context cannot be reconciled to declarations."""


def _evidence_for_affected(
    behaviors: BehaviorDocument,
    affected: frozenset[str],
) -> tuple[set[EvidenceClass], set[EvidenceClass]]:
    required: set[EvidenceClass] = set()
    conditional: set[EvidenceClass] = set()
    for behavior in behaviors.behaviors:
        if behavior.behavior_id not in affected:
            continue
        required.update(behavior.required_evidence)
        conditional.update(behavior.conditional_evidence)
    return required, conditional


def generate_agent_guidance(
    *,
    manifest: RepositoryManifest,
    profile: QualityProfile,
    behaviors: BehaviorDocument,
    inventory: TestInventory,
    affected_behavior_ids: tuple[str, ...],
    gap_findings: tuple[GapFinding, ...],
) -> AgentTestingGuidance:
    """Generate bounded deterministic guidance without model inference."""
    if (
        manifest.profile.profile_id != profile.profile_id
        or manifest.profile.version != profile.version
    ):
        raise GuidanceError("manifest/profile binding mismatch")
    if not affected_behavior_ids:
        raise GuidanceError("at least one affected behavior is required")

    affected = frozenset(affected_behavior_ids)
    known = {item.behavior_id for item in behaviors.behaviors}
    unknown = affected - known
    if unknown:
        raise GuidanceError(
            "affected behavior IDs are not declared: " + ", ".join(sorted(unknown))
        )

    required, conditional = _evidence_for_affected(behaviors, affected)
    relevant_tests = tuple(
        GuidanceTest(
            test_id=item.test_id,
            evidence_class=item.evidence_class,
            behavior_ids=tuple(sorted(set(item.behavior_ids) & affected)),
        )
        for item in sorted(inventory.tests, key=lambda test: test.test_id)
        if set(item.behavior_ids) & affected
    )

    affected_journeys = tuple(
        GuidanceJourney(
            journey_id=item.journey_id,
            behavior_ids=item.behavior_ids,
            required_evidence=item.required_evidence,
        )
        for item in sorted(
            behaviors.critical_journeys,
            key=lambda journey: journey.journey_id,
        )
        if set(item.behavior_ids) & affected
    )
    for journey in affected_journeys:
        required.update(journey.required_evidence)

    relevant_subjects = set(affected)
    relevant_subjects.update(
        f"journey:{item.journey_id}"
        for item in affected_journeys
    )
    relevant_gaps = tuple(
        item
        for item in sorted(gap_findings, key=lambda finding: finding.behavior_id)
        if item.behavior_id in relevant_subjects
    )
    gaps_by_subject = {item.behavior_id: item for item in relevant_gaps}
    missing_gap_subjects = relevant_subjects - set(gaps_by_subject)
    if missing_gap_subjects:
        raise GuidanceError(
            "guidance requires complete affected behavior/journey findings; missing: "
            + ", ".join(sorted(missing_gap_subjects))
        )

    relevant_evidence_ids = tuple(
        sorted(
            {
                evidence_id
                for gap in relevant_gaps
                for evidence_id in gap.evidence_ids
            }
        )
    )
    covered_classes = {item.evidence_class for item in relevant_tests}
    missing_classes = required - covered_classes

    states = {item.state for item in relevant_gaps}
    all_proven = states == {EvidenceState.PROVEN}

    next_actions: list[str] = []
    if all_proven:
        next_actions.append(
            "No new test is required: existing evidence is proven for the current "
            "repository revision and profile."
        )
    else:
        if EvidenceState.STALE in states:
            next_actions.append(
                "Re-run the declared verification suites at the current exact SHA; "
                "stale evidence cannot prove the change."
            )
        if EvidenceState.NOT_EVALUABLE in states:
            next_actions.append(
                "Restore evaluability before adding coverage; environment/tool failure "
                "must not be converted into a passing result."
            )
        if EvidenceState.MISSING in states and missing_classes:
            next_actions.append(
                "Add or extend the smallest behavior-focused test/evidence needed for: "
                + ", ".join(sorted(item.value for item in missing_classes))
            )
        elif EvidenceState.MISSING in states:
            next_actions.append(
                "Prefer extending or repairing existing relevant tests before creating "
                "another overlapping test."
            )

    suite_ids = tuple(
        sorted(
            suite.suite_id
            for suite in manifest.suites
            if set(suite.evidence_classes) & required
        )
    )

    return AgentTestingGuidance(
        repository=inventory.repository,
        sha=inventory.sha,
        profile=manifest.profile,
        affected_behavior_ids=tuple(sorted(affected)),
        required_evidence=tuple(sorted(required, key=lambda item: item.value)),
        conditional_evidence=tuple(
            sorted(conditional, key=lambda item: item.value)
        ),
        relevant_tests=relevant_tests,
        relevant_evidence_ids=relevant_evidence_ids,
        relevant_gaps=relevant_gaps,
        critical_journeys=affected_journeys,
        suite_ids_to_verify=suite_ids,
        new_test_needed=(
            EvidenceState.MISSING in states and bool(missing_classes)
        ),
        next_actions=tuple(next_actions),
        anti_patterns=(
            "Do not add a coverage-only test that proves no declared behavior.",
            "Do not delete a test solely from an advisory value classification.",
            "Do not duplicate existing behavior evidence without a distinct failure mode.",
            "Do not replace focused unit/integration evidence with E2E-only coverage.",
            "Do not widen executor trust or request credentials from agent guidance.",
        ),
    )
