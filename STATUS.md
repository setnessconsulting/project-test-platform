# Status

## Repository state

Implementation foundation in progress on API-372.

## Implemented

- Python 3.12+ package and console entry point
- version reporting
- bounded credential-free doctor command with JSON output
- canonical local/CI verification runner
- high-confidence public-safety scanner
- public repository security boundary
- architecture, security, contribution, and agent guidance
- package boundaries for future discovery, inventory, adapters, analysis, planning,
  evidence, and reporting work
- synthetic unit tests for doctor, CLI JSON, and public-safety behavior

## Not yet implemented

The following capabilities remain planned under later API-371 children and must not be
represented as complete:

- versioned Quality Profiles and public schemas
- target repository manifest validation
- behavior and critical-journey declarations
- test-framework discovery and inventory
- pytest, Vitest/Jest, Playwright, Pester, and JUnit adapters
- test-value, gap, flake, freshness, mutation, and quality-policy analysis
- execution trust policy and deterministic ExecutionPlans
- QualityReceipt generation and validation
- GitHub Actions placement analysis
- Jenkins execution integration
- stable full CLI/reporting surface
- AI-agent testing guidance
- Portfolio Graph quality export/consumer integration
- representative real-repository qualification
- Jenkins same-SHA cutover qualification
- live qualification and maintenance-mode closeout

## Evidence semantics

Passing repository tests is repository/synthetic evidence only. It is not evidence that
Jenkins, GitHub Actions migration, Portfolio Graph consumption, or any live provider path is
qualified.
