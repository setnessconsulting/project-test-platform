"""Fully local synthetic qualification of the Jenkins consumer contract (API-390).

The primary path proves::

    ExecutionPlan -> Jenkins adapter -> synthetic executor result
        -> QualityReceipt -> Test Platform validation

with no live Jenkins controller, no GitHub Actions, no provider credentials,
no deployment, and no live GitHub mutation. Every artifact it produces is
marked synthetic so it can never be mistaken for live qualification.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from test_platform.contracts import (
    Diagnostic,
    DiagnosticSeverity,
    ExecutionPlan,
    ExecutionTrustClass,
    JenkinsConsumerContract,
    JenkinsExecutionMode,
    JenkinsExecutionRequest,
    JenkinsReceiptSubmission,
    ProfileBinding,
    QualityReceipt,
    RepositoryManifest,
    SuiteDefinition,
)
from test_platform.integration.catalog import load_consumer_contract
from test_platform.integration.compile import compile_jenkins_execution_request
from test_platform.integration.ingest import ingest_jenkins_receipt_submission
from test_platform.planning.core import (
    ExecutionEvent,
    PlanningContext,
    compile_execution_plan,
)
from test_platform.profiles import load_profile

SYNTHETIC_REPOSITORY = "setnessconsulting/project-test-platform"
SYNTHETIC_SHA = "0" * 39 + "a"
SYNTHETIC_PROFILE = ProfileBinding(profile_id="infrastructure-tool-v1", version="1.0.0")
SYNTHETIC_BEHAVIORS_PATH = "quality/behaviors.yaml"

SYNTHETIC_MANIFEST = RepositoryManifest(
    schema_version="1",
    profile=SYNTHETIC_PROFILE,
    behaviors_path=SYNTHETIC_BEHAVIORS_PATH,
    suites=(
        SuiteDefinition(
            suite_id="verify",
            entrypoint="verify",
            trust=ExecutionTrustClass.PR_UNTRUSTED,
            timeout_seconds=1800,
            evidence_classes=(
                "static",
                "deterministic",
                "integration",
                "adversarial-security",
            ),
        ),
    ),
)

SYNTHETIC_RESULTS: tuple[dict[str, object], ...] = (
    {
        "suite_id": "verify",
        "executor_id": "container-infrastructure",
        "status": "passed",
        "observed_repository": SYNTHETIC_REPOSITORY,
        "observed_sha": SYNTHETIC_SHA,
        "passed_tests": 412,
        "failed_tests": 0,
        "skipped_tests": 3,
        "duration_seconds": 12.5,
        "artifacts": ["verify/verify.log", "verify/results.json"],
        "tool_versions": [{"name": "node", "version": "22.23.3"}],
    },
)


@dataclass(frozen=True)
class SyntheticQualification:
    """A deterministic synthetic plan/request pair used by the harness."""

    plan: ExecutionPlan
    request: JenkinsExecutionRequest
    contract: JenkinsConsumerContract


def synthetic_manifest(trust: ExecutionTrustClass) -> RepositoryManifest:
    """Return the synthetic manifest bound to one trust class."""
    return SYNTHETIC_MANIFEST.model_copy(
        update={
            "suites": tuple(
                suite.model_copy(update={"trust": trust}) for suite in SYNTHETIC_MANIFEST.suites
            )
        }
    )


def build_synthetic_qualification(
    *,
    trust: ExecutionTrustClass = ExecutionTrustClass.PR_UNTRUSTED,
) -> SyntheticQualification:
    """Compile a deterministic synthetic plan and its Jenkins request."""
    contract = load_consumer_contract()
    profile = load_profile(SYNTHETIC_PROFILE.profile_id)
    compiled = compile_execution_plan(
        repository=SYNTHETIC_REPOSITORY,
        sha=SYNTHETIC_SHA,
        profile=profile,
        manifest=synthetic_manifest(trust),
        trust=trust,
        policy_version="1",
        context=PlanningContext(event=ExecutionEvent.PULL_REQUEST),
    )
    request = compile_jenkins_execution_request(
        compiled.plan,
        contract,
        execution_mode=JenkinsExecutionMode.SYNTHETIC_QUALIFICATION,
    )
    return SyntheticQualification(plan=compiled.plan, request=request, contract=contract)


def synthetic_diagnostics(receipts: Sequence[QualityReceipt]) -> tuple[Diagnostic, ...]:
    """Return bounded, clearly synthetic qualification diagnostics."""
    return (
        Diagnostic(
            code="qualification.synthetic",
            severity=DiagnosticSeverity.INFO,
            message=(
                "Synthetic local qualification: no Jenkins controller, GitHub Actions "
                "run, provider credential, or live qualification evidence was used."
            ),
            evidence_ids=tuple(receipt.receipt_id for receipt in receipts),
        ),
    )


def write_json(path: Path, value: object) -> None:
    """Write a deterministic pretty-printed JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _finalize(
    adapter: Sequence[str],
    request_path: Path,
    results_path: Path,
    submission_path: Path,
) -> None:
    completed = subprocess.run(  # noqa: S603
        [*adapter, "finalize", str(request_path), str(results_path), str(submission_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(
            "jenkins adapter rejected the synthetic qualification: "
            f"{completed.stderr.strip()}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the local synthetic plan -> adapter -> receipt -> validation path."""
    parser = argparse.ArgumentParser(
        description="Run the local synthetic Jenkins contract qualification."
    )
    parser.add_argument(
        "--adapter",
        nargs="+",
        required=True,
        help="Command that runs the project-jenkins adapter CLI, e.g. node src/cli.mjs",
    )
    parser.add_argument("--report", type=Path, help="Optional normalized report path.")
    parser.add_argument(
        "--workdir",
        type=Path,
        default=Path(".jenkins-qualification"),
        help="Directory for the synthetic request, results, and submission.",
    )
    args = parser.parse_args(argv)

    qualification = build_synthetic_qualification()
    workdir = args.workdir.resolve()
    write_json(workdir / "execution-request.json", qualification.request.model_dump(mode="json"))
    write_json(workdir / "executor-results.json", list(SYNTHETIC_RESULTS))
    submission_path = workdir / "receipt-submission.json"
    _finalize(
        args.adapter,
        workdir / "execution-request.json",
        workdir / "executor-results.json",
        submission_path,
    )

    submission = JenkinsReceiptSubmission.model_validate_json(
        submission_path.read_text(encoding="utf-8")
    )
    receipts, diagnostics = ingest_jenkins_receipt_submission(
        qualification.request, submission, qualification.contract
    )
    report = {
        "qualification": "synthetic",
        "live_qualification": False,
        "contract_id": qualification.request.contract_id,
        "contract_version": qualification.request.contract_version,
        "plan_id": qualification.request.plan.plan_id,
        "repository": qualification.request.plan.repository,
        "sha": qualification.request.plan.sha,
        "trust": qualification.request.plan.trust.value,
        "receipt_ids": [receipt.receipt_id for receipt in receipts],
        "results": [receipt.result.value for receipt in receipts],
        "diagnostics": [diagnostic.code for diagnostic in diagnostics],
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }
    text = json.dumps(report, indent=2) + "\n"
    if args.report:
        write_json(args.report, report)
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
