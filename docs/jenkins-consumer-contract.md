# Jenkins consumer contract

## Purpose

This document describes the versioned integration contract by which Test Platform
`ExecutionPlan`s are consumed by Jenkins and returned as validated `QualityReceipt`s.
It is the contract implemented by API-390.

The flow is:

    Test Platform compiles a deterministic ExecutionPlan
        -> compiles a versioned JenkinsExecutionRequest
        -> Jenkins adapter verifies and resolves the request against the closed catalog
        -> Jenkins executes the approved suites with Jenkins-owned command tokens
        -> Jenkins adapter normalizes outcomes and builds a JenkinsReceiptSubmission
        -> Test Platform re-derives every receipt and validates the submission

Test Platform plans and evaluates. Jenkins executes. Neither side reinterprets the
other's authority.

## Authority boundaries

### Test Platform owns

- the canonical `JenkinsConsumerContract` catalog (`data/contracts/v1/jenkins-execution-contract.yaml`);
- the `JenkinsExecutionRequest` and `JenkinsReceiptSubmission` schemas;
- plan-to-request compilation (`integration/compile.py`);
- the normalized outcome-to-result mapping (`integration/outcomes.py`);
- receipt ingestion and re-derivation (`integration/ingest.py`);
- quality evaluation.

### project-jenkins owns

- the trusted adapter (`integration/test-platform-contract/src/`);
- the approved catalog mirror (`src/approved-catalog.json`);
- the trusted Pipeline fragment (`casc/pipelines/test-platform.groovy`);
- controller configuration, agents, credentials, and GitHub Check publication;
- actual execution and operational recovery.

A target repository cannot add, widen, or re-point a suite, executor, entrypoint,
capability, agent class, artifact, or timeout. Executor entries carry no command
strings: the adapter resolves an approved `executor_id` to centrally maintained
Jenkins logic, so no pull request can inject shell.

## Exact-SHA semantics

Every request binds an exact repository identity and a full commit SHA
(`JenkinsExpectedHead`). The binding is enforced at three points:

1. compilation refuses a plan whose repository is not centrally approved;
2. the adapter re-verifies the request head against the plan before resolving;
3. ingestion re-checks the submission head, the plan identity, and every
   observed head.

A foreign observed head is only ever reported through the head-dependent
normalized statuses (`stale-head`, `checkout-sha-mismatch`, `cancelled`), which
explicitly signal "not evidence for the bound head" and can never normalize to a
pass. A pass or a real test failure observed at a different SHA is rejected
outright. Stale-head handling may only normalize to `blocked` or
`not-evaluable`, never to a pass.

## Trust model

The plan's trust class (`pr-untrusted`, `trusted-branch`, `trusted-manual`,
`live-qualification`) determines the maximum capability ceiling the adapter may
grant. The compiler derives the trust grant from the plan; it can never widen it.
Untrusted PR code cannot receive production/provider credentials, and live
qualification surfaces (live artifacts, live evidence classes) require
`live-qualification` trust. The adapter re-checks the grant against its own
allowlist on every request, so a forged or widened grant fails closed.

## Failure mapping

Test Platform ships the normalized result table inside every execution request.
The consumer applies it verbatim; it never chooses a result itself.

| Adapter status             | Result          |
|----------------------------|-----------------|
| `passed`                   | `pass`          |
| `failed`                   | `fail`          |
| `agent-unavailable`        | `blocked`       |
| `controller-unavailable`   | `blocked`       |
| `timed-out`                | `blocked`       |
| `cancelled`                | `blocked`       |
| `stale-head`               | `blocked`       |
| `checkout-sha-mismatch`    | `blocked`       |
| `unsupported-capability`   | `blocked`       |
| `rejected-trust`           | `blocked`       |
| `malformed-result`         | `not-evaluable` |

Infrastructure failure never becomes a pass. A passing result with failing tests
is rejected. A result mapping that flattens an outage to a pass is rejected at
request verification.

## Jenkins adapter ownership

The adapter is centrally maintained controller logic. It:

- accepts structured, approved data only;
- never interpolates repository-controlled text into a command;
- never resolves a credential;
- never decides what an outcome means;
- re-derives receipt identity exactly as Test Platform derives it, so a forged
  receipt fails ingestion.

The trusted Pipeline authorizes the request on the controller before any
checkout, executes each approved suite with static Jenkins-owned command tokens,
and finalizes one normalized submission. Controller-to-agent file handoff uses
`stash`/`unstash`; no repository-controlled value crosses that boundary.

## Evidence handoff

Artifact declarations are bounded (count, bytes, relative path, evidence
class). Evidence references must be declared by the approved suite binding, and
live evidence additionally requires live-qualification trust, a controller
execution mode, and a live evidence origin. Diagnostics are bounded in count and
message length.

## Synthetic qualification

The primary local qualification path proves the full flow without a live Jenkins
controller, GitHub Actions, provider credentials, or deployment:

    python -m test_platform.integration.qualification --adapter <adapter command>

It compiles a deterministic synthetic plan, runs the real project-jenkins adapter
over it, and ingests the resulting submission. Every artifact it produces is
marked synthetic. Passing these synthetic tests does **not** prove Jenkins
infrastructure, parity, cutover, or rollback readiness.

## Version and compatibility policy

The contract is versioned at three levels:

- `contract_version` (currently `1.0.0`) identifies the canonical catalog;
- `plan_schema_versions` and `receipt_schema_versions` list the supported
  document schema versions;
- the request and submission carry their own `schema_version`.

Consumers must pin a contract version they were qualified against. An unknown or
mismatched contract identity, plan schema version, or receipt schema version
fails closed. Schema evolution is additive within a major contract line: new
optional fields may be added, but a consumer must reject any schema version it
was not qualified against rather than guess. A breaking change requires a new
contract version and re-qualification of every consumer before its evidence is
accepted.

## What remains outstanding

Live Jenkins qualification is explicitly **not** part of this contract work and
remains with CONSULTING-347 (Jenkins infrastructure, shadow parity, cutover, and
rollback) and the live-qualification follow-up (API-395). In particular, the
following remain outstanding:

- controller image rebuild with the pinned Node runtime and adapter;
- live same-SHA execution against a real target repository;
- agent/controller failure and cancellation behavior under the real controller;
- GitHub Check publication of normalized receipts;
- cutover and rollback proof under the Jenkins authority.

Synthetic contract tests are necessary but not sufficient for those gates.
