# Status

## Repository state

The repo-local public-safe core is implemented through API-392 on the current CLI/guidance branch.
The remaining API-371 work is intentionally concentrated in cross-repository integration, real
pilot qualification, migration parity, adversarial release hardening, and final closeout.

## Implemented foundation and policy

- Python 3.12+ public-safe package and canonical clean-room verification
- strict versioned contracts and generated JSON Schema
- eight explicit Quality Profiles
- repository manifest, behavior, and critical-journey contracts
- execution trust classes and credential-safe live qualification policy

## Implemented discovery and analysis

- bounded pytest/Jest/Vitest/Playwright/Pester discovery
- normalized test inventory and bounded result adapters
- advisory evidence-backed test-value analysis
- behavior/journey gap analysis
- history, duration, flake, and freshness semantics
- selective bounded mutation/fault evidence
- deterministic quality evaluation and exact-scope waivers

## Implemented execution/evidence layer

- exact-SHA deterministic ExecutionPlan compilation
- mandatory profile/behavior evidence cannot be skipped by change-scope optimization
- undeclared suite and trust escalation rejection
- plan-bound QualityReceipt generation and validation
- semantic receipt IDs and explicit replay detection
- live-evidence trust enforcement
- evidence-based GitHub Actions workflow placement
- routine deployment migrates to Jenkins via move-deployment-to-jenkins once qualified,
  otherwise fails closed; security/fallback lanes retained deliberately
- hosted verification and deployment minutes separated
- no savings claim from incomplete usage evidence

## CLI/reporting/guidance implemented on current branch

- stable validate/inventory/behaviors/audit/gaps/plan/evaluate/actions commands
- stable migration-plan/report/portfolio-export/doctor commands
- deterministic guide command for AI-agent testing guidance
- versioned JSON command envelope and bounded Markdown summaries
- explicit tool/profile/contract identity in relevant outputs
- non-zero gate/error exit semantics
- offline fixture operation with no credential requirement
- public-safe path/sensitive-field redaction
- complete QualityExport generation that fails closed on partial behavior evidence
- deterministic affected-behavior guidance with critical-journey obligations
- no-new-test guidance when exact current evidence is already proven
- no automatic deletion, trust widening, or model-inferred canonical facts

## Remaining epic work

Implemented since the last revision: API-390 (Jenkins ExecutionPlan/QualityReceipt
consumer contract), API-401 (deployment placement migrates to Jenkins when qualified),
API-396 (Phase A core adversarial hardening).

API-396 Phase A hardened the core against hostile input and closed four verified
violations of the stated critical invariants:

- the evaluator could aggregate a `NOT_APPLICABLE` behavior gap to `PASS`
- `validate_quality_receipt` never recomputed the receipt identity, so forged
  identifiers bypassed the replay ledger
- the public-safety scanner and discovery walk were unbounded and followed symlinks
- public-safe output only redacted whole-value paths, leaking the operator host path
  to stderr on every malformed-manifest run

Also fixed: dead `live_evidence_max_age_days` enforcement, all-skipped suites
aggregating to `PASS`, `evaluate` passing with behavior analysis omitted, waiver
scope not bound to a revision, lax `min_length=7` SHA contracts, incomplete secret
patterns, and unqualified platform-revision binding for qualification evidence.

Limits and the explicitly unclosed boundaries are documented in
`docs/adversarial-limits.md` and `SECURITY.md`. The plan → request → receipt chain
remains unauthenticated; that attestation work is API-399.

- API-393: project-portfolio-graph QualityExport consumer integration (export side
  complete; consumer side pending in project-portfolio-graph)
- API-394: four representative real-repository qualifications (pilot manifests pending)
- API-395: same-SHA Jenkins shadow parity/fallback and safe Actions migration proof
  (gated on CONSULTING-355 Jenkins GO)
- API-398: portfolio-wide Test Platform + Jenkins onboarding and CI/CD migration
  (gated on API-394, API-395, API-401, and CONSULTING-368)
- API-399: Phase B integration adversarial hardening, including cryptographic
  attestation of the plan → request → receipt chain
- API-397: exact-SHA V1 qualification, release, and maintenance-mode transition
- API-400: bounded exact-SHA CI fallback for frozen project-jira-api (separate lane;
  excluded from the API-398 active-repository set)

## Evidence semantics

Passing repository/synthetic verification does not establish Jenkins, GitHub Actions migration,
Portfolio Graph consumption, or any live provider path as qualified. API-397 must remain
open until its prerequisite integration and pilot evidence exists. API-399 owns attestation
of live-provider claims.
