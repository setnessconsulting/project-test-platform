# Status

## Repository state

API-372/API-373/API-374/API-375/API-376/API-377/API-386 are complete. API-378 bounded discovery is implemented on this branch pending clean-room verification.

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

## Implemented policy layer

- eight explicit versioned Quality Profiles
- strict .test-platform.yaml manifest parsing and profile binding
- repository-local behavior and critical-journey declarations
- path/symlink and arbitrary-entrypoint rejection
- execution trust classes, capability matrix, and live-qualification gates
- public-safe cross-stack examples

## Discovery implemented on current branch

- bounded deterministic repository indexing
- versioned discovery plugin registry
- static pytest/Jest/Vitest/Playwright/Pester detection
- explicit UNKNOWN/MALFORMED/LIMIT_EXCEEDED states
- no repository test execution or dependency installation

## Not yet implemented

The following capabilities remain planned under later API-371 children and must not be
represented as complete:

- normalized test inventory
- pytest, Vitest/Jest, Playwright, Pester, and JUnit adapters
- test-value, gap, flake, freshness, mutation, and quality-policy analysis
- deterministic ExecutionPlans
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
