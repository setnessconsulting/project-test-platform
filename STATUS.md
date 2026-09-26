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
- deployment/security/fallback lanes retained deliberately
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

- API-390: project-jenkins ExecutionPlan/QualityReceipt consumer integration
- API-393: project-portfolio-graph QualityExport consumer integration
- API-394: four representative real-repository qualifications
- API-395: same-SHA Jenkins shadow parity/fallback and safe Actions migration proof
- API-396: final adversarial hardening after primary integrations/pilots
- API-397: exact-SHA V1 qualification, release, and maintenance-mode transition

## Evidence semantics

Passing repository/synthetic verification does not establish Jenkins, GitHub Actions migration,
Portfolio Graph consumption, or any live provider path as qualified. API-396/API-397 must remain
open until their prerequisite integration and pilot evidence exists.
