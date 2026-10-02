# Completion Contract — project-test-platform

**Standard:** Portfolio Completion Standard v1
**Date:** 2026-09-27

## Intended outcome

Public-safe core for portfolio-wide behavioral verification, quality
evidence, test-value analysis, qualification policy, and CI placement. "Use
the lowest-cost test layer that truthfully proves a behavior."

## Jobs to be done

Provide the public-safe core for portfolio-wide behavioral verification.

## Required functionality

Python 3.12+ package, CLI, doctor diagnostics, public-safety scanner,
versioned contracts, eight Quality Profiles, repository manifest/behavior/
critical-journey contracts, execution trust classes, bounded
pytest/Jest/Vitest/Playwright/Pester discovery, normalized test inventory,
advisory test-value analysis, deterministic quality evaluation, exact-SHA
ExecutionPlan compilation, QualityReceipt generation, evidence-based GitHub
Actions workflow placement.

## Automated verification

```
python -m test_platform.verify
```

## External/runtime checks

None (policy/analysis tool, no deployment). Public GitHub clean-room
verification.

## Stability evidence

Repository-local public-safe core implemented through API-392, plus API-390
(Jenkins ExecutionPlan/QualityReceipt consumer contract), API-401 (deployment
placement migrates to Jenkins when qualified), and the API-396 Phase A core
adversarial suite.

## Acceptable limitations

API-393 (Portfolio Graph QualityExport consumer integration), API-394 (four
representative real-repository qualifications), API-395 (Jenkins shadow
parity/fallback), API-398 (portfolio-wide onboarding and CI/CD migration),
API-399 (Phase B integration adversarial hardening), API-397 (exact-SHA V1
qualification, release, maintenance-mode transition) all remaining. API-400
(bounded exact-SHA CI fallback for frozen project-jira-api) is a separate lane
excluded from the active-repository rollout set. See STATUS.md for the current
remaining-work detail.

## Post-completion operating mode

Active development. Core is delivered; consumer integration is the current
gap.
