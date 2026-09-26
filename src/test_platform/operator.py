"""Offline operator services used by the stable CLI."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from test_platform.analysis import (
    BehaviorEvidenceObservation,
    analyze_behavior_gaps,
    evaluate_quality,
)
from test_platform.behaviors import load_behavior_document
from test_platform.contracts import (
    BehaviorDocument,
    DiscoveryReport,
    EvidenceClass,
    EvidenceState,
    GapFinding,
    ProfileBinding,
    QualityAssessment,
    QualityProfile,
    RepositoryManifest,
    TestInventory,
    Waiver,
)
from test_platform.discovery import discover_repository
from test_platform.inventory import InventoryBuildResult, build_inventory
from test_platform.manifest import load_manifest
from test_platform.planning import (
    ActionsPlacementReport,
    WorkflowObservation,
    analyze_actions_placement,
)
from test_platform.profiles import load_profile


class OperatorError(ValueError):
    """Raised when an operator input cannot be interpreted safely."""


@dataclass(frozen=True)
class RepositoryContext:
    """Validated repository-local policy context."""

    root: Path
    manifest: RepositoryManifest
    profile: QualityProfile
    behaviors: BehaviorDocument


def load_repository_context(root: Path) -> RepositoryContext:
    """Load manifest, exact built-in profile, and declared behaviors."""
    manifest = load_manifest(root / ".test-platform.yaml")
    profile = load_profile(manifest.profile.profile_id)
    behaviors = load_behavior_document(root / manifest.behaviors_path)
    return RepositoryContext(
        root=root,
        manifest=manifest,
        profile=profile,
        behaviors=behaviors,
    )


def parse_behavior_links(value: Any) -> dict[str, tuple[str, ...]]:
    """Parse an explicit test-id to behavior-id mapping."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise OperatorError("behavior links must be a JSON object")
    result: dict[str, tuple[str, ...]] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not isinstance(raw, list):
            raise OperatorError("behavior links must map strings to string arrays")
        if not all(isinstance(item, str) for item in raw):
            raise OperatorError("behavior links must contain only string behavior IDs")
        result[key] = tuple(sorted(set(cast(list[str], raw))))
    return result


def build_repository_inventory(
    context: RepositoryContext,
    *,
    repository: str,
    sha: str,
    behavior_links: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[DiscoveryReport, InventoryBuildResult]:
    """Run bounded discovery and normalize an inventory."""
    discovery = discover_repository(context.root)
    inventory = build_inventory(
        repository=repository,
        sha=sha,
        discovery=discovery,
        behavior_links=behavior_links,
    )
    return discovery, inventory


def parse_behavior_evidence(value: Any) -> tuple[BehaviorEvidenceObservation, ...]:
    """Parse explicit behavior evidence observations from JSON-compatible data."""
    if not isinstance(value, list):
        raise OperatorError("behavior evidence must be a JSON array")

    result: list[BehaviorEvidenceObservation] = []
    required_keys = {
        "evidence_id",
        "subject_id",
        "evidence_class",
        "state",
        "sha",
        "profile",
    }
    for raw in value:
        if not isinstance(raw, dict) or set(raw) != required_keys:
            raise OperatorError(
                "each behavior evidence item must contain exactly the documented fields"
            )
        profile_raw = raw["profile"]
        if not isinstance(profile_raw, dict):
            raise OperatorError("behavior evidence profile must be an object")
        try:
            profile = ProfileBinding.model_validate(profile_raw)
            result.append(
                BehaviorEvidenceObservation(
                    evidence_id=str(raw["evidence_id"]),
                    subject_id=str(raw["subject_id"]),
                    evidence_class=EvidenceClass(str(raw["evidence_class"])),
                    state=EvidenceState(str(raw["state"])),
                    sha=str(raw["sha"]),
                    profile=profile,
                )
            )
        except (ValidationError, ValueError) as exc:
            raise OperatorError("invalid behavior evidence item") from exc
    return tuple(result)


def parse_gap_findings(value: Any) -> tuple[GapFinding, ...]:
    """Parse GapFinding contracts from a bounded JSON value."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise OperatorError("gap findings must be a JSON array")
    try:
        return tuple(GapFinding.model_validate(item) for item in value)
    except ValidationError as exc:
        raise OperatorError("invalid gap finding") from exc


def parse_rule_states(value: Any) -> dict[str, EvidenceState]:
    """Parse explicit profile rule states."""
    if not isinstance(value, dict):
        raise OperatorError("rule states must be a JSON object")
    states: dict[str, EvidenceState] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not isinstance(raw, str):
            raise OperatorError("rule states must map rule IDs to evidence-state strings")
        try:
            states[key] = EvidenceState(raw)
        except ValueError as exc:
            raise OperatorError(f"invalid evidence state for rule {key}") from exc
    return states


def parse_waivers(value: Any) -> tuple[Waiver, ...]:
    """Parse exact-scope waiver contracts."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise OperatorError("waivers must be a JSON array")
    try:
        return tuple(Waiver.model_validate(item) for item in value)
    except ValidationError as exc:
        raise OperatorError("invalid waiver") from exc


def parse_workflow_observations(value: Any) -> tuple[WorkflowObservation, ...]:
    """Parse allowlisted sanitized workflow observations."""
    if not isinstance(value, list):
        raise OperatorError("workflow observations must be a JSON array")

    allowed = {
        "workflow_id",
        "evidence_intent",
        "verification",
        "deployment",
        "github_native",
        "security_native",
        "manual_fallback",
        "equivalent_plan_coverage",
        "jenkins_capable",
        "duplicate_of",
        "hosted_minutes",
        "usage_complete",
    }
    result: list[WorkflowObservation] = []
    for raw in value:
        if not isinstance(raw, dict) or not set(raw).issubset(allowed):
            raise OperatorError("workflow observation contains unsupported fields")
        if "workflow_id" not in raw or "evidence_intent" not in raw:
            raise OperatorError("workflow_id and evidence_intent are required")
        intent = raw["evidence_intent"]
        if not isinstance(intent, list) or not all(
            isinstance(item, str) for item in intent
        ):
            raise OperatorError("evidence_intent must be a string array")
        hosted = raw.get("hosted_minutes")
        if hosted is not None and not isinstance(hosted, (int, float)):
            raise OperatorError("hosted_minutes must be numeric or null")
        result.append(
            WorkflowObservation(
                workflow_id=str(raw["workflow_id"]),
                evidence_intent=tuple(cast(list[str], intent)),
                verification=bool(raw.get("verification", False)),
                deployment=bool(raw.get("deployment", False)),
                github_native=bool(raw.get("github_native", False)),
                security_native=bool(raw.get("security_native", False)),
                manual_fallback=bool(raw.get("manual_fallback", False)),
                equivalent_plan_coverage=bool(
                    raw.get("equivalent_plan_coverage", False)
                ),
                jenkins_capable=bool(raw.get("jenkins_capable", False)),
                duplicate_of=(
                    str(raw["duplicate_of"])
                    if raw.get("duplicate_of") is not None
                    else None
                ),
                hosted_minutes=float(hosted) if hosted is not None else None,
                usage_complete=bool(raw.get("usage_complete", False)),
            )
        )
    return tuple(result)


def parse_quality_assessment(value: Any) -> QualityAssessment:
    """Parse one QualityAssessment contract."""
    try:
        return QualityAssessment.model_validate(value)
    except ValidationError as exc:
        raise OperatorError("invalid quality assessment") from exc


def parse_test_inventory(value: Any) -> TestInventory:
    """Parse one TestInventory contract."""
    try:
        return TestInventory.model_validate(value)
    except ValidationError as exc:
        raise OperatorError("invalid test inventory") from exc


def parse_receipt_ids(value: Any) -> tuple[str, ...]:
    """Parse a bounded list of receipt IDs."""
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise OperatorError("receipt IDs must be a JSON string array")
    return tuple(sorted(set(cast(list[str], value))))


def analyze_gaps_from_context(
    context: RepositoryContext,
    observations: tuple[BehaviorEvidenceObservation, ...],
    *,
    sha: str,
) -> tuple[GapFinding, ...]:
    """Evaluate full declared behavior/journey state for an exact SHA."""
    return analyze_behavior_gaps(
        context.behaviors,
        observations,
        sha=sha,
        profile=context.manifest.profile,
    )


def evaluate_from_context(
    context: RepositoryContext,
    *,
    repository: str,
    sha: str,
    rule_states: Mapping[str, EvidenceState],
    gaps: tuple[GapFinding, ...],
    waivers: tuple[Waiver, ...],
    applicable_conditional_rules: frozenset[str],
    blocked_reasons: tuple[str, ...],
    now: datetime,
) -> QualityAssessment:
    """Evaluate current repository quality from explicit inputs."""
    return evaluate_quality(
        repository=repository,
        sha=sha,
        profile=context.profile,
        rule_states=rule_states,
        behavior_gaps=gaps,
        waivers=waivers,
        applicable_conditional_rules=applicable_conditional_rules,
        blocked_reasons=blocked_reasons,
        now=now,
    )


def actions_report(
    observations: tuple[WorkflowObservation, ...],
) -> ActionsPlacementReport:
    """Analyze sanitized workflow placement observations."""
    return analyze_actions_placement(observations)
