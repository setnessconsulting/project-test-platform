# ADR 0001: Authority model

Status: Accepted for V1.

## Decision

Project Test Platform is the portfolio-wide authority for shared testing policy, Quality
Profiles, behavioral evidence contracts, deterministic quality evaluation, execution
planning, QualityReceipt contracts, and public-safe quality exports.

It is not the authority for repository production tests, CI infrastructure, provider
credentials, repository lifecycle, or portfolio topology.

## Authority matrix

| Concern | Authority |
| --- | --- |
| Shared testing philosophy and policy | project-test-platform |
| Quality Profile definitions | project-test-platform |
| Behavior/evidence/plan/receipt contracts | project-test-platform |
| Repository-specific code and tests | target repository |
| Repository-specific behavior declarations | target repository |
| Repository Test Platform manifest | target repository |
| Jenkins controller, agents, credentials, execution | project-jenkins |
| GitHub Checks emitted by Jenkins | project-jenkins |
| Provider authentication and mutations | provider control-plane repositories |
| Repository identity, routing, lifecycle | project-meta |
| Cross-portfolio graph and maintenance/readiness consumption | project-portfolio-graph |

## Consequences

- Test Platform may plan and evaluate execution but does not execute CI jobs itself.
- Jenkins may execute plans and emit receipts but does not define quality policy.
- Portfolio Graph consumes sanitized quality evidence and does not parse executor logs.
- Target repositories keep their actual tests and fixtures local.
- No provider or executor is allowed to widen authority from repository-controlled text.
