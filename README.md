# Project Test Platform

Project Test Platform is the public-safe core for portfolio-wide behavioral verification,
quality evidence, test-value analysis, qualification policy, and CI placement.

The project is being implemented under API-371 in the API Platform Jira project.

## Core principle

Use the lowest-cost test layer that truthfully proves a behavior, while requiring assembled
end-to-end evidence for critical user journeys and integration boundaries.

This project does not optimize for test count or line coverage. Unit, contract, integration,
end-to-end, adversarial, live, performance, and manual evidence each have appropriate uses.

## Authority boundary

Project Test Platform owns shared testing policy, versioned Quality Profiles, behavior and
evidence contracts, deterministic quality evaluation, execution planning, normalized
QualityReceipts, and public-safe quality exports.

It does not own:

- repository production code or repository-specific tests;
- Jenkins controllers, agents, credentials, or job execution;
- provider credentials or provider mutation;
- Portfolio Graph portfolio relationships;
- project-meta repository identity or lifecycle;
- deployment orchestration or background scheduling.

See ARCHITECTURE.md and SECURITY.md before implementation work.

## Current implemented foundation

API-372 establishes:

- Python 3.12+ packaging and test-platform CLI;
- bounded credential-free doctor diagnostics;
- canonical verification entry point;
- public-safety scanner for high-confidence secrets and private paths;
- architecture/security/contribution/agent guidance;
- package boundaries for discovery, inventory, analysis, planning, evidence, adapters, and reporting;
- public GitHub clean-room verification.

Run after installing the dev dependencies:

    python -m test_platform.verify

Basic CLI:

    test-platform --version
    test-platform doctor
    test-platform doctor --json

## Public repository safety

Treat every committed byte as permanently public. A later visibility change does not retract
clones, forks, screenshots, caches, or previously distributed history.

Do not commit credentials, private repository inventories, raw private Jenkins logs,
user-specific machine paths, customer or learner data, proprietary production fixtures,
private vulnerability findings, or raw private qualification evidence.

## Status

See STATUS.md for implemented and planned capability. The repository should not claim a
provider, Jenkins, Portfolio Graph, or live qualification capability until the corresponding
Jira issue has passed its own evidence gates.
