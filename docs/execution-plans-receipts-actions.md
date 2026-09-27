# Execution plans, receipts, and GitHub Actions placement

## Execution plans

A plan is compiled from validated profile, manifest, behavior evidence requirements, event/trust
context, and platform policy. Planning requires a full exact repository SHA.

Repository-controlled text cannot add an undeclared suite. Each selected suite is a symbolic
manifest entrypoint rather than an arbitrary command string.

Required profile/behavior evidence cannot be skipped by change-scope optimization. Planning fails
closed if no trust-compatible suite provides a mandatory evidence class.

The plan ID binds event and live-target context semantically even though V1 keeps that orchestration
context outside the language-neutral ExecutionPlan contract.

## Quality receipts

Executors return a QualityReceipt bound to the exact plan, repository, SHA, profile, suite, trust
class, result, evidence, and tool versions.

Receipt IDs ignore generation time but not semantic evidence. Replaying an already-consumed receipt
can be rejected explicitly by the consumer ledger. A PASS receipt cannot report failed tests.

Non-live plans cannot claim live qualification evidence.

## Jenkins consumer contract

A compiled plan is bound to the versioned Jenkins consumer contract
(`data/contracts/v1/jenkins-execution-contract.yaml`) before it can be executed by Jenkins.
Compilation resolves every planned suite against the closed catalog, binds the exact
repository and SHA, derives the trust grant, and refuses capability or trust escalation.
The Jenkins adapter consumes only structured, approved data and returns a normalized
receipt submission that Test Platform re-derives and validates. See
`docs/jenkins-consumer-contract.md` for the full contract, failure mapping, and version
policy.

## GitHub Actions placement

Workflow placement is advisory and evidence-driven. Cost alone never decides placement.

- deployment work is retained as deployment;
- GitHub-native/security-hosted work remains on GitHub;
- owner-controlled fallback lanes remain fallback;
- routine verification moves to Jenkins only after equivalent Test Platform plan coverage and
  Jenkins capability are established;
- duplicate removal requires explicit duplicate identity plus equivalent evidence intent.

Hosted verification and deployment minutes are reported separately. If usage coverage is
incomplete, savings remain unknown rather than estimated as fact.

This module produces placement decisions only. It never disables or edits a GitHub workflow.
