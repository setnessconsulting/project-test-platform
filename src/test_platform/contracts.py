"""Versioned public contract models for Test Platform V1."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Evidence is only meaningful when it names one exact immutable revision. A
# short or non-hex identifier cannot bind anything, so every contract that
# claims to be revision-bound uses this single definition.
_EXACT_SHA_PATTERN = r"^[0-9a-f]{40,64}$"


def exact_sha_field(description: str = "exact repository revision") -> Any:
    """Return the canonical exact-SHA field used by every revision-bound contract."""
    return Field(
        min_length=40,
        max_length=64,
        pattern=_EXACT_SHA_PATTERN,
        description=description,
    )


class ContractModel(BaseModel):
    """Strict immutable base for public contract models."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    semantic_exclude: ClassVar[frozenset[str]] = frozenset()

    def semantic_payload(self) -> dict[str, object]:
        """Return the content used when a stable semantic identity is required."""
        return self.model_dump(mode="json", exclude=set(self.semantic_exclude))


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


class ExecutionTarget(StrEnum):
    LOCAL = "local"
    JENKINS = "jenkins"
    GITHUB_ACTIONS = "github-actions"
    MANUAL_LIVE = "manual-live"


class TrustCapability(StrEnum):
    REPOSITORY_READ = "repository-read"
    TEST_EXECUTION = "test-execution"
    SYNTHETIC_FIXTURES = "synthetic-fixtures"
    PRIVATE_EVIDENCE_WRITE = "private-evidence-write"
    BOUNDED_TEST_CREDENTIALS = "bounded-test-credentials"
    BOUNDED_PROVIDER_CREDENTIALS = "bounded-provider-credentials"
    LIVE_PROVIDER_READ = "live-provider-read"


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
    # Legacy value retained for reading historical evidence only. The current
    # classifier never emits it: routine deployment workflows migrate to
    # Jenkins via MOVE_DEPLOYMENT_TO_JENKINS once qualified, and otherwise
    # fail closed as NOT_EVALUATED. See API-401.
    RETAIN_DEPLOYMENT = "retain-deployment"
    MOVE_DEPLOYMENT_TO_JENKINS = "move-deployment-to-jenkins"
    MANUAL_FALLBACK = "manual-fallback"
    REMOVE_DUPLICATE = "remove-duplicate"
    NOT_EVALUATED = "not-evaluated"


class DiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiscoveryState(StrEnum):
    DETECTED = "detected"
    UNKNOWN = "unknown"
    MALFORMED = "malformed"
    LIMIT_EXCEEDED = "limit-exceeded"


class FrameworkDiscovery(ContractModel):
    framework: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    adapter_version: str = Field(min_length=1)
    state: DiscoveryState
    config_paths: tuple[str, ...] = ()
    test_paths: tuple[str, ...] = ()
    command_ids: tuple[str, ...] = ()
    result_formats: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


class DiscoveryReport(ContractModel):
    schema_version: Literal["1"] = "1"
    state: DiscoveryState
    frameworks: tuple[FrameworkDiscovery, ...]
    files_scanned: int = Field(ge=0)
    truncated: bool = False
    diagnostics: tuple[str, ...] = ()


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
    profile_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    version: str = Field(min_length=1)
    requirements: tuple[ProfileRequirement, ...]
    allowed_trust: tuple[ExecutionTrustClass, ...]
    recommended_execution: tuple[ExecutionTarget, ...]
    live_evidence_max_age_days: int | None = Field(default=None, ge=1)
    critical_journey_e2e_required: bool = False
    mutation_analysis: RequirementLevel = RequirementLevel.NOT_APPLICABLE

    @model_validator(mode="after")
    def validate_profile_policy(self) -> Self:
        """Require stable unique rules and explicit executor/trust policy."""
        rule_ids = [requirement.rule_id for requirement in self.requirements]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("profile rule IDs must be unique")
        if not self.allowed_trust:
            raise ValueError("profile must declare at least one allowed trust class")
        if not self.recommended_execution:
            raise ValueError("profile must declare at least one recommended execution target")
        return self


class ProfileBinding(ContractModel):
    profile_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    version: str = Field(min_length=1)


class SuiteDefinition(ContractModel):
    suite_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
    entrypoint: str = Field(
        min_length=1,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$",
    )
    trust: ExecutionTrustClass
    timeout_seconds: int = Field(default=600, ge=1, le=86_400)
    evidence_classes: tuple[EvidenceClass, ...] = ()


class Behavior(ContractModel):
    behavior_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_.:-]*$")
    description: str = Field(min_length=1)
    criticality: Criticality
    required_evidence: tuple[EvidenceClass, ...] = Field(min_length=1)
    conditional_evidence: tuple[EvidenceClass, ...] = ()


class CriticalJourney(ContractModel):
    journey_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_.:-]*$")
    description: str = Field(min_length=1)
    behavior_ids: tuple[str, ...] = Field(min_length=1)
    required_evidence: tuple[EvidenceClass, ...] = (EvidenceClass.E2E,)


class BehaviorDocument(ContractModel):
    schema_version: Literal["1"] = "1"
    behaviors: tuple[Behavior, ...]
    critical_journeys: tuple[CriticalJourney, ...] = ()

    @model_validator(mode="after")
    def validate_identity_and_references(self) -> Self:
        """Require unique IDs and valid journey references."""
        behavior_ids = [behavior.behavior_id for behavior in self.behaviors]
        if len(behavior_ids) != len(set(behavior_ids)):
            raise ValueError("behavior IDs must be unique")

        journey_ids = [journey.journey_id for journey in self.critical_journeys]
        if len(journey_ids) != len(set(journey_ids)):
            raise ValueError("critical journey IDs must be unique")

        for behavior in self.behaviors:
            if len(behavior.required_evidence) != len(set(behavior.required_evidence)):
                raise ValueError(
                    f"behavior {behavior.behavior_id} repeats a required evidence class"
                )

        known = set(behavior_ids)
        for journey in self.critical_journeys:
            if len(journey.behavior_ids) != len(set(journey.behavior_ids)):
                raise ValueError(
                    f"critical journey {journey.journey_id} repeats a behavior reference"
                )
            missing = set(journey.behavior_ids) - known
            if missing:
                raise ValueError(
                    f"critical journey {journey.journey_id} references unknown behaviors: "
                    + ", ".join(sorted(missing))
                )
            if EvidenceClass.E2E not in journey.required_evidence:
                raise ValueError(
                    f"critical journey {journey.journey_id} must require end-to-end evidence"
                )
        return self


class RepositoryManifest(ContractModel):
    schema_version: Literal["1"] = "1"
    profile: ProfileBinding
    behaviors_path: str = Field(min_length=1)
    suites: tuple[SuiteDefinition, ...]

    @model_validator(mode="after")
    def validate_suite_ids(self) -> Self:
        """Require stable unique suite IDs."""
        suite_ids = [suite.suite_id for suite in self.suites]
        if len(suite_ids) != len(set(suite_ids)):
            raise ValueError("suite IDs must be unique")
        return self


class TestCaseObservation(ContractModel):
    test_id: str = Field(min_length=1)
    framework: str = Field(min_length=1)
    path: str | None = None
    behavior_ids: tuple[str, ...] = ()
    evidence_class: EvidenceClass


class TestInventory(ContractModel):
    schema_version: Literal["1"] = "1"
    repository: str = Field(min_length=1)
    sha: str = exact_sha_field()
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
    sha: str = exact_sha_field()
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
    sha: str = exact_sha_field()
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
    sha: str = exact_sha_field()
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
    sha: str = exact_sha_field()
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
    sha: str = exact_sha_field()
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


class TrustPolicyDecision(ContractModel):
    trust: ExecutionTrustClass
    requested: tuple[TrustCapability, ...]
    allowed: bool
    denied: tuple[TrustCapability, ...] = ()
    reason: str = Field(min_length=1)


class Diagnostic(ContractModel):
    code: str = Field(min_length=1)
    severity: DiagnosticSeverity
    message: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = ()


# --- Jenkins consumer integration contract (API-390) -------------------------
#
# Test Platform owns every model in this block. project-jenkins carries only a
# minimal generated/versioned consumer representation of these documents; it
# must not reimplement them or reinterpret their semantics.


JENKINS_CONTRACT_ID = "jenkins-execution-contract"


class ExecutorCapability(StrEnum):
    """Bounded capability a centrally configured executor image must provide."""

    DOCKER = "docker"
    NODE_22 = "node-22"
    NODE_24 = "node-24"
    PLAYWRIGHT_CHROMIUM = "playwright-chromium"
    NETWORK_ISOLATED = "network-isolated"
    PRIVATE_EVIDENCE_STORE = "private-evidence-store"


class ArtifactKind(StrEnum):
    """Bounded artifact classes an executor may declare and hand off."""

    LOG = "log"
    JUNIT_XML = "junit-xml"
    RESULT_JSON = "result-json"
    COVERAGE = "coverage"
    SCREENSHOT = "screenshot"


class EvidenceOrigin(StrEnum):
    """Where the evidence that produced a receipt actually came from."""

    SYNTHETIC = "synthetic"
    CONTROLLER_RECORDED = "controller-recorded"
    LIVE = "live"


class JenkinsExecutionMode(StrEnum):
    """Whether a submission came from a local harness or a real controller run."""

    SYNTHETIC_QUALIFICATION = "synthetic-qualification"
    CONTROLLER_EXECUTION = "controller-execution"


class JenkinsExecutionStatus(StrEnum):
    """Normalized Jenkins adapter outcome vocabulary."""

    PASSED = "passed"
    FAILED = "failed"
    AGENT_UNAVAILABLE = "agent-unavailable"
    CONTROLLER_UNAVAILABLE = "controller-unavailable"
    TIMED_OUT = "timed-out"
    CANCELLED = "cancelled"
    STALE_HEAD = "stale-head"
    CHECKOUT_SHA_MISMATCH = "checkout-sha-mismatch"
    UNSUPPORTED_CAPABILITY = "unsupported-capability"
    REJECTED_TRUST = "rejected-trust"
    MALFORMED_RESULT = "malformed-result"


class StaleHeadOutcome(StrEnum):
    """Permitted normalized result when a plan requires current-head binding."""

    BLOCKED = "blocked"
    NOT_EVALUABLE = "not-evaluable"


_SAFE_REPOSITORY = r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9._-]{1,100}$"
_SAFE_ARTIFACT_PATH = r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$"


class JenkinsContractLimits(ContractModel):
    """Hard upper bounds applied to every consumer request and submission."""

    max_suites: int = Field(ge=1, le=256)
    max_artifacts_per_suite: int = Field(ge=0, le=64)
    max_artifact_bytes: int = Field(ge=1, le=1_073_741_824)
    max_evidence_references_per_suite: int = Field(ge=0, le=64)
    max_diagnostics_per_outcome: int = Field(ge=0, le=32)
    max_diagnostic_message_length: int = Field(ge=1, le=2_048)
    max_suite_timeout_seconds: int = Field(ge=1, le=86_400)
    max_execution_seconds: int = Field(ge=1, le=604_800)


class JenkinsExecutorBinding(ContractModel):
    """A centrally configured executor identity and its hard capability ceiling.

    Executor identifiers are closed identifiers, never commands. A target
    repository cannot add, widen, or re-point an entry in this catalog.
    """

    executor_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    capabilities: tuple[ExecutorCapability, ...] = Field(min_length=1)
    max_trust: ExecutionTrustClass
    agent_class: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$")

    @model_validator(mode="after")
    def validate_capabilities(self) -> Self:
        """Reject repeated capabilities so ceilings stay unambiguous."""
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("executor capabilities must be unique")
        return self


class JenkinsArtifactDeclaration(ContractModel):
    """One bounded, relative artifact a suite is permitted to hand off."""

    artifact_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    kind: ArtifactKind
    path: str = Field(min_length=1, max_length=128, pattern=_SAFE_ARTIFACT_PATH)
    max_bytes: int = Field(ge=1, le=1_073_741_824)
    live: bool = False
    evidence_class: EvidenceClass

    @model_validator(mode="after")
    def validate_relative_path(self) -> Self:
        """Reject traversal, absolute, and symlink-shaped artifact paths."""
        segments = self.path.split("/")
        if any(segment in {"", ".", ".."} for segment in segments):
            raise ValueError("artifact path must be a bounded relative path")
        return self


class JenkinsSuiteBinding(ContractModel):
    """Approved mapping from a declared suite to a closed executor entrypoint.

    The entrypoint is a catalog identifier resolved by centrally maintained
    Jenkins logic. It is never a shell string supplied by a target repository,
    and a plan whose declared entrypoint differs from the catalog is rejected.
    """

    suite_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
    entrypoint: str = Field(
        min_length=1,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$",
    )
    executor_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    required_capabilities: tuple[ExecutorCapability, ...] = ()
    evidence_classes: tuple[EvidenceClass, ...] = Field(min_length=1)
    timeout_seconds: int = Field(default=600, ge=1, le=86_400)
    artifacts: tuple[JenkinsArtifactDeclaration, ...] = ()

    @model_validator(mode="after")
    def validate_artifacts(self) -> Self:
        """Require unique bounded artifact identities and declarations."""
        artifact_ids = [artifact.artifact_id for artifact in self.artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("suite artifact identities must be unique")
        paths = [artifact.path for artifact in self.artifacts]
        if len(paths) != len(set(paths)):
            raise ValueError("suite artifact paths must be unique")
        return self


class JenkinsConsumerContract(ContractModel):
    """Canonical, versioned Jenkins consumer contract owned by Test Platform."""

    schema_version: Literal["1"] = "1"
    contract_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    contract_version: str = Field(min_length=1, pattern=r"^\d+\.\d+\.\d+$")
    plan_schema_versions: tuple[str, ...] = Field(min_length=1)
    receipt_schema_versions: tuple[str, ...] = Field(min_length=1)
    repositories: tuple[str, ...] = ()
    executors: tuple[JenkinsExecutorBinding, ...] = Field(min_length=1)
    suites: tuple[JenkinsSuiteBinding, ...] = Field(min_length=1)
    limits: JenkinsContractLimits

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        """Require closed, unique executor/suite identities and resolvable refs."""
        executor_ids = [executor.executor_id for executor in self.executors]
        if len(executor_ids) != len(set(executor_ids)):
            raise ValueError("executor identities must be unique")
        suite_ids = [suite.suite_id for suite in self.suites]
        if len(suite_ids) != len(set(suite_ids)):
            raise ValueError("suite identities must be unique")
        known_executors = set(executor_ids)
        for suite in self.suites:
            if suite.executor_id not in known_executors:
                raise ValueError(
                    f"suite {suite.suite_id} references unknown executor "
                    f"{suite.executor_id}"
                )
            if len(suite.evidence_classes) != len(set(suite.evidence_classes)):
                raise ValueError(f"suite {suite.suite_id} repeats an evidence class")
            if len(suite.artifacts) > self.limits.max_artifacts_per_suite:
                raise ValueError(
                    f"suite {suite.suite_id} exceeds the declared artifact bound"
                )
            if suite.timeout_seconds > self.limits.max_suite_timeout_seconds:
                raise ValueError(
                    f"suite {suite.suite_id} exceeds the declared timeout bound"
                )
            for artifact in suite.artifacts:
                if artifact.max_bytes > self.limits.max_artifact_bytes:
                    raise ValueError(
                        f"suite {suite.suite_id} artifact {artifact.artifact_id} "
                        "exceeds the declared artifact byte bound"
                    )
        return self


class JenkinsCancellationPolicy(ContractModel):
    """Bounded cancellation semantics the consumer must honour."""

    cancel_on_superseded_head: bool = True
    cancel_on_newer_plan: bool = True
    abandon_workspace_on_cancel: bool = True


class JenkinsStaleHeadPolicy(ContractModel):
    """Bounded stale-head semantics; stale execution can never become a pass."""

    require_current_head: bool = True
    on_stale_head: StaleHeadOutcome = StaleHeadOutcome.BLOCKED
    max_head_age_seconds: int = Field(default=3_600, ge=0, le=604_800)


class JenkinsOutcomeResultRule(ContractModel):
    """Test Platform-owned mapping from adapter status to normalized result.

    The consumer applies this table verbatim. It never chooses a result itself,
    so an executor can never turn an infrastructure failure into a pass.
    """

    status: JenkinsExecutionStatus
    result: QualityResult

    @model_validator(mode="after")
    def validate_mapping(self) -> Self:
        """Keep infrastructure and malformed states out of the pass vocabulary."""
        if self.status is not JenkinsExecutionStatus.PASSED and self.result in {
            QualityResult.PASS,
        }:
            raise ValueError("only a passed status may map to a pass result")
        if (
            self.status is JenkinsExecutionStatus.FAILED
            and self.result is not QualityResult.FAIL
        ):
            raise ValueError("a failed status must map to a fail result")
        return self


class JenkinsExpectedHead(ContractModel):
    """Exact repository/SHA binding a consumer must verify before execution."""

    repository: str = Field(min_length=1, max_length=140, pattern=_SAFE_REPOSITORY)
    sha: str = Field(min_length=40, max_length=64, pattern=r"^[0-9a-f]{40,64}$")


class JenkinsTrustGrant(ContractModel):
    """Maximum capability set the consumer may grant for this plan."""

    trust: ExecutionTrustClass
    capabilities: tuple[TrustCapability, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_grant(self) -> Self:
        """Require an unambiguous, duplicate-free capability grant."""
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("trust grant capabilities must be unique")
        return self


class JenkinsExecutionRequest(ContractModel):
    """The complete, versioned document a Jenkins adapter consumes.

    It carries only structured, centrally approved data: a canonical
    ExecutionPlan plus the resolved executor mapping, capability ceiling,
    artifact declarations, and cancellation/stale-head semantics.
    """

    schema_version: Literal["1"] = "1"
    contract_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    contract_version: str = Field(min_length=1, pattern=r"^\d+\.\d+\.\d+$")
    plan_schema_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    execution_mode: JenkinsExecutionMode
    head: JenkinsExpectedHead
    plan: ExecutionPlan
    trust_grant: JenkinsTrustGrant
    suites: tuple[JenkinsSuiteBinding, ...] = Field(min_length=1)
    required_capabilities: tuple[ExecutorCapability, ...] = ()
    result_mapping: tuple[JenkinsOutcomeResultRule, ...] = Field(min_length=1)
    cancellation: JenkinsCancellationPolicy = JenkinsCancellationPolicy()
    stale_head: JenkinsStaleHeadPolicy = JenkinsStaleHeadPolicy()
    max_execution_seconds: int = Field(default=7_200, ge=1, le=604_800)
    # Qualification evidence must be attributable to the exact Test Platform
    # revision that minted it, so a result produced under different policy
    # logic cannot be presented as current.
    platform_version: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Fail closed on head, trust, and mapping divergence from the plan."""
        if self.plan.schema_version != self.plan_schema_version:
            raise ValueError("request plan schema version does not match the plan")
        if self.head.repository != self.plan.repository:
            raise ValueError("request head repository does not match the plan")
        if self.head.sha != self.plan.sha:
            raise ValueError("request head SHA does not match the plan")
        if self.trust_grant.trust is not self.plan.trust:
            raise ValueError("trust grant does not match the plan trust class")
        if len(self.suites) != len(self.plan.suites):
            raise ValueError("request suite bindings must cover the planned suites")
        if [suite.suite_id for suite in self.suites] != [
            suite.suite_id for suite in self.plan.suites
        ]:
            raise ValueError("request suite bindings must follow the planned order")
        statuses = [rule.status for rule in self.result_mapping]
        if len(statuses) != len(set(statuses)):
            raise ValueError("result mapping statuses must be unique")
        if JenkinsExecutionStatus.PASSED not in statuses:
            raise ValueError("result mapping must cover a passed status")
        if len(self.suites) > 256:
            raise ValueError("request exceeds the bounded suite count")
        return self

    def result_for(self, status: JenkinsExecutionStatus) -> QualityResult:
        """Return the Test Platform-owned normalized result for a status."""
        for rule in self.result_mapping:
            if rule.status is status:
                return rule.result
        raise ValueError(f"no normalized result is defined for {status.value}")


class JenkinsDiagnostic(ContractModel):
    """One bounded, non-authoritative consumer diagnostic."""

    code: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    severity: DiagnosticSeverity
    message: str = Field(min_length=1, max_length=2_048)


class JenkinsObservedHead(ContractModel):
    """The repository/SHA the consumer actually observed at execution time."""

    repository: str = Field(min_length=1, max_length=140, pattern=_SAFE_REPOSITORY)
    sha: str = Field(min_length=40, max_length=64, pattern=r"^[0-9a-f]{40,64}$")


class JenkinsSuiteOutcome(ContractModel):
    """Normalized per-suite consumer outcome carrying a canonical receipt."""

    schema_version: Literal["1"] = "1"
    suite_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
    executor_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    status: JenkinsExecutionStatus
    observed_head: JenkinsObservedHead
    receipt: QualityReceipt
    diagnostics: tuple[JenkinsDiagnostic, ...] = ()

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        """Require the receipt to agree with the reported suite and executor."""
        if self.receipt.suite_id != self.suite_id:
            raise ValueError("receipt suite identity does not match the outcome")
        if self.receipt.executor != self.executor_id:
            raise ValueError("receipt executor does not match the outcome")
        if self.receipt.schema_version != "1":
            raise ValueError("unsupported receipt schema version")
        return self


class JenkinsReceiptSubmission(ContractModel):
    """The complete, versioned document a Jenkins adapter returns."""

    schema_version: Literal["1"] = "1"
    contract_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    contract_version: str = Field(min_length=1, pattern=r"^\d+\.\d+\.\d+$")
    plan_id: str = Field(min_length=1)
    head: JenkinsObservedHead
    execution_mode: JenkinsExecutionMode
    evidence_origin: EvidenceOrigin
    outcomes: tuple[JenkinsSuiteOutcome, ...] = Field(min_length=1)
    generated_at: datetime
    # The Test Platform revision that produced this submission. Ingestion
    # refuses a submission minted by a different revision than the request,
    # so evidence cannot be carried across a change in platform policy logic.
    platform_version: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_submission(self) -> Self:
        """Require unique suite outcomes so replayed receipts cannot hide."""
        suite_ids = [outcome.suite_id for outcome in self.outcomes]
        if len(suite_ids) != len(set(suite_ids)):
            raise ValueError("receipt submission suite outcomes must be unique")
        return self


PUBLIC_SCHEMA_MODELS: tuple[type[ContractModel], ...] = (
    FrameworkDiscovery,
    DiscoveryReport,
    EvidenceReference,
    ProfileRequirement,
    QualityProfile,
    ProfileBinding,
    SuiteDefinition,
    Behavior,
    CriticalJourney,
    BehaviorDocument,
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
    TrustPolicyDecision,
    Diagnostic,
    JenkinsContractLimits,
    JenkinsExecutorBinding,
    JenkinsArtifactDeclaration,
    JenkinsSuiteBinding,
    JenkinsConsumerContract,
    JenkinsCancellationPolicy,
    JenkinsStaleHeadPolicy,
    JenkinsOutcomeResultRule,
    JenkinsExpectedHead,
    JenkinsTrustGrant,
    JenkinsExecutionRequest,
    JenkinsDiagnostic,
    JenkinsObservedHead,
    JenkinsSuiteOutcome,
    JenkinsReceiptSubmission,
)
