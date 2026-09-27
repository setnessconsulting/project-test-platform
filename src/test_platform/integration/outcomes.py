"""Normalized Jenkins failure semantics owned by Test Platform.

The adapter never decides what an execution outcome *means*. Test Platform
ships the mapping inside every execution request and the consumer applies it
verbatim, so an executor, an agent failure, or a controller outage can never
be turned into a pass.
"""

from __future__ import annotations

from test_platform.contracts import (
    JenkinsExecutionStatus,
    JenkinsOutcomeResultRule,
    QualityResult,
)

OUTCOME_RESULT_MAPPING: tuple[JenkinsOutcomeResultRule, ...] = (
    JenkinsOutcomeResultRule(status=JenkinsExecutionStatus.PASSED, result=QualityResult.PASS),
    JenkinsOutcomeResultRule(status=JenkinsExecutionStatus.FAILED, result=QualityResult.FAIL),
    JenkinsOutcomeResultRule(
        status=JenkinsExecutionStatus.AGENT_UNAVAILABLE, result=QualityResult.BLOCKED
    ),
    JenkinsOutcomeResultRule(
        status=JenkinsExecutionStatus.CONTROLLER_UNAVAILABLE, result=QualityResult.BLOCKED
    ),
    JenkinsOutcomeResultRule(status=JenkinsExecutionStatus.TIMED_OUT, result=QualityResult.BLOCKED),
    JenkinsOutcomeResultRule(status=JenkinsExecutionStatus.CANCELLED, result=QualityResult.BLOCKED),
    JenkinsOutcomeResultRule(
        status=JenkinsExecutionStatus.STALE_HEAD, result=QualityResult.BLOCKED
    ),
    JenkinsOutcomeResultRule(
        status=JenkinsExecutionStatus.CHECKOUT_SHA_MISMATCH, result=QualityResult.BLOCKED
    ),
    JenkinsOutcomeResultRule(
        status=JenkinsExecutionStatus.UNSUPPORTED_CAPABILITY, result=QualityResult.BLOCKED
    ),
    JenkinsOutcomeResultRule(
        status=JenkinsExecutionStatus.REJECTED_TRUST, result=QualityResult.BLOCKED
    ),
    JenkinsOutcomeResultRule(
        status=JenkinsExecutionStatus.MALFORMED_RESULT, result=QualityResult.NOT_EVALUABLE
    ),
)

OUTCOME_DESCRIPTIONS: dict[JenkinsExecutionStatus, str] = {
    JenkinsExecutionStatus.PASSED: "suite completed and reported no failing test",
    JenkinsExecutionStatus.FAILED: "suite completed and reported at least one failing test",
    JenkinsExecutionStatus.AGENT_UNAVAILABLE: "no build agent satisfied the approved binding",
    JenkinsExecutionStatus.CONTROLLER_UNAVAILABLE: (
        "controller could not schedule or observe the run"
    ),
    JenkinsExecutionStatus.TIMED_OUT: "suite exceeded its approved bounded timeout",
    JenkinsExecutionStatus.CANCELLED: "run was cancelled by cancellation policy",
    JenkinsExecutionStatus.STALE_HEAD: "observed head is no longer the bound current head",
    JenkinsExecutionStatus.CHECKOUT_SHA_MISMATCH: "checkout did not produce the bound exact SHA",
    JenkinsExecutionStatus.UNSUPPORTED_CAPABILITY: "executor lacks a required approved capability",
    JenkinsExecutionStatus.REJECTED_TRUST: "trust policy rejected the requested execution",
    JenkinsExecutionStatus.MALFORMED_RESULT: "executor result could not be interpreted",
}
