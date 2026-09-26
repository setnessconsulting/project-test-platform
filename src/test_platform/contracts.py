"""Versioned public contract models for Test Platform V1."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    """Strict immutable base for public contract models."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    semantic_exclude: ClassVar[frozenset[str]] = frozenset()

    def semantic_payload(self) -> dict[str, object]:
        """Return the content used when a stable semantic identity is required."""
        return self.model_dump(mode="json", exclude=self.semantic_exclude)


class EvidenceClass(StrEnum):
    STATIC = "static"
    DETERMINISTIC = "deterministic"
    CONTRACT = "contract"
    INTEGRATION = "integration"
    E2E = "end-to-end"
    ADVERSARIAL = "adversarial-security"
    LIVE = "live-qualification"
    PERFORMANCE = "performance"
    MANUAL = "manual-owner-gate"


class EvidenceState(StrEnum):
    PROVEN = "proven"
    MISSING = "missing"
    STALE = "stale"
    NOT_EVALUABLE = "not-evaluable"
    NOT_APPLICABLE = "not-applicable"


class RequirementLevel(StrEnum):
    REQUIRED = "required"
    CONDITIONAL = "conditional"
    INFORMATIONAL = "informational"
    NOT_APPLICABLE = "not-applicable"


class Criticality(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExecutionTrustClass(StrEnum):
    PR_UNTRUSTED = "pr-untrusted"
    TRUSTED_BRANCH = "trusted-branch"
    TRUSTED_MANUAL = "trusted-manual"
    LIVE_QUALIFICATION = "live-qualification"


class QualityResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUABLE = "not-evaluable"
    BLOCKED = "blocked"


class TestValueClassification(StrEnum):
    REQUIRED = "required"
    USEFUL = "useful"
    POSSIBLY_REDUNDANT = "possibly-redundant"
    TRIVIAL = "trivial"
    IMPLEMENTATION_COUPLED = "implementation-coupled"
    FLAKY = "flaky"
    OBSOLETE = "obsolete"
    UNKNOWN = "unknown"


class WorkflowPlacement(StrEnum):
    MOVE_TO_JENKINS = "move-to-jenkins"
    RETAIN_GITHUB = "retain-github"
    RETAIN_DEPLOYMENT = "retain-deployment"
    MANUAL_FALLBACK = "manual-fallback"
    REMOVE_DUPLICATE = "remove-duplicate"
    NOT_EVALUATED = "not-evaluated"


class DiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EvidenceReference(ContractModel):
    evidence_id: str = Field(min_length=1)
    evidence_class: EvidenceClass
    live: bool = False
    source: str = Field(min_length=1)
    reference: str | None = None


class ProfileRequirement(ContractModel):
    rule_id: str = Field(min_length=1)
    evidence_class: EvidenceClass
    level: RequirementLevel
    non_waivable: bool = False
    description: str = Field(min_length=1)


class QualityProfile(ContractModel):
    schema_version: Literal["1"] = "1"
    profile_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    requirements: tuple[ProfileRequirement, ...]


class ProfileBinding(ContractModel):
    profile_id: str = Field(min_length=1)
    version: str = Field(min_length=1)


class SuiteDefinition(ContractModel):
    suite_id: str = Field(min_length=1)
    entrypoint: str = Field(min_length=1)
    trust: ExecutionTrustClass
    timeout_seconds: int = Field(default=600, ge=1, le=86_400)
    evidence_classes: tuple[EvidenceClass, ...] = ()


class Behavior(ContractModel):
    behavior_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    criticality: Criticality
    required_evidence: tuple[EvidenceClass, ...]
    conditional_evidence: tuple[EvidenceClass, ...] = ()


class CriticalJourney(ContractModel):
    journey_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    behavior_ids: tuple[str, ...]
    required_evidence: tuple[EvidenceClass, ...] = (EvidenceClass.E2E,)


class RepositoryManifest(ContractModel):
    schema_version: Literal["1"] = "1"
    profile: ProfileBinding
    behaviors_path: str = Field(min_length=1)
    suites: tuple[SuiteDefinition, ...]


class TestCaseObservation(ContractModel):
    test_id: str = Field(min_length=1)
    framework: str = Field(min_length=1)
    path: str | None = None
    behavior_ids: tuple[str, ...] = ()
    evidence_class: EvidenceClass


class TestInventory(ContractModel):
    schema_version: Literal["1"] = "1"
    repository: str = Field(min_length=1)
    sha: str = Field(min_length=7)
    tests: tuple[TestCaseObservation, ...]


class TestValueFinding(ContractModel):
    finding_id: str = Field(min_length=1)
    test_id: str = Field(min_length=1)
    classification: TestValueClassification
    reasons: tuple[str, ...]
    evidence_ids: tuple[str, ...] = ()


class GapFinding(ContractModel):
    finding_id: str = Field(min_length=1)
    behavior_id: str = Field(min_length=1)
    state: EvidenceState
    reasons: tuple[str, ...]
    evidence_ids: tuple[str, ...] = ()


class TestRunSample(ContractModel):
    sha: str = Field(min_length=7)
    result: QualityResult
    duration_seconds: float = Field(ge=0)
    executor: str = Field(min_length=1)
    trust: ExecutionTrustClass
    attempt: int = Field(default=1, ge=1)


class FlakeHistory(ContractModel):
    test_id: str = Field(min_length=1)
    samples: tuple[TestRunSample, ...]


class EvidenceFreshness(ContractModel):
    state: EvidenceState
    reason: str = Field(min_length=1)
    qualified_sha: str | None = None


class ExecutionPlan(ContractModel):
    schema_version: Literal["1"] = "1"
    plan_id: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    sha: str = Field(min_length=7)
    profile: ProfileBinding
    trust: ExecutionTrustClass
    policy_version: str = Field(min_length=1)
    suites: tuple[SuiteDefinition, ...]


class ToolVersion(ContractModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)


class QualityReceipt(ContractModel):
    semantic_exclude: ClassVar[frozenset[str]] = frozenset({"generated_at"})

    schema_version: Literal["1"] = "1"
    receipt_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    sha: str = Field(min_length=7)
    profile: ProfileBinding
    suite_id: str = Field(min_length=1)
    executor: str = Field(min_length=1)
    trust: ExecutionTrustClass
    result: QualityResult
    passed_tests: int = Field(default=0, ge=0)
    failed_tests: int = Field(default=0, ge=0)
    skipped_tests: int = Field(default=0, ge=0)
    duration_seconds: float = Field(default=0, ge=0)
    evidence: tuple[EvidenceReference, ...] = ()
    tool_versions: tuple[ToolVersion, ...] = ()
    generated_at: datetime


class QualityAssessment(ContractModel):
    schema_version: Literal["1"] = "1"
    assessment_id: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    sha: str = Field(min_length=7)
    profile: ProfileBinding
    result: QualityResult
    gaps: tuple[GapFinding, ...] = ()
    test_value_findings: tuple[TestValueFinding, ...] = ()
    waiver_ids: tuple[str, ...] = ()


class WorkflowPlacementDecision(ContractModel):
    workflow_id: str = Field(min_length=1)
    placement: WorkflowPlacement
    reason: str = Field(min_length=1)


class QualityExport(ContractModel):
    semantic_exclude: ClassVar[frozenset[str]] = frozenset({"generated_at"})

    schema_version: Literal["1"] = "1"
    export_id: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    sha: str = Field(min_length=7)
    profile: ProfileBinding
    result: QualityResult
    required_behaviors: int = Field(ge=0)
    proven_behaviors: int = Field(ge=0)
    not_evaluable_behaviors: int = Field(ge=0)
    critical_journeys_required: int = Field(default=0, ge=0)
    critical_journeys_proven: int = Field(default=0, ge=0)
    critical_journeys_not_evaluable: int = Field(default=0, ge=0)
    receipt_ids: tuple[str, ...] = ()
    generated_at: datetime


class Waiver(ContractModel):
    schema_version: Literal["1"] = "1"
    waiver_id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    owner_decision_ref: str = Field(min_length=1)
    created_at: datetime
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def expiry_follows_creation(self) -> Self:
        """Reject a waiver whose expiry is not later than creation."""
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")
        return self


class Diagnostic(ContractModel):
    code: str = Field(min_length=1)
    severity: DiagnosticSeverity
    message: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = ()


PUBLIC_SCHEMA_MODELS: tuple[type[ContractModel], ...] = (
    EvidenceReference,
    ProfileRequirement,
    QualityProfile,
    ProfileBinding,
    SuiteDefinition,
    Behavior,
    CriticalJourney,
    RepositoryManifest,
    TestCaseObservation,
    TestInventory,
    TestValueFinding,
    GapFinding,
    TestRunSample,
    FlakeHistory,
    EvidenceFreshness,
    ExecutionPlan,
    ToolVersion,
    QualityReceipt,
    QualityAssessment,
    WorkflowPlacementDecision,
    QualityExport,
    Waiver,
    Diagnostic,
)
