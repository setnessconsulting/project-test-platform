# Architecture

## Purpose

Project Test Platform is the portfolio-wide authority for testing policy, behavioral
evidence contracts, quality profiles, deterministic quality evaluation, execution planning,
and normalized quality receipts.

It does not own repository production tests or CI infrastructure.

## Authority boundaries

- Target repositories own their code, tests, fixtures, behavior declarations, and manifest.
- Project Test Platform owns shared testing policy, profile contracts, analysis, plans,
  normalized receipts, and public-safe quality exports.
- Project Jenkins owns Jenkins controllers, agents, credentials, isolation, job execution,
  GitHub Check publication, recovery, and fallback.
- Project Portfolio Graph owns cross-portfolio relationships and maintenance/readiness
  consumption of normalized quality evidence.
- Project Meta owns portfolio repository identity, routing, and lifecycle.
- Provider control planes own provider authentication and provider operations.

## Core principle

Use the lowest-cost test layer that truthfully proves a behavior. Require assembled
end-to-end evidence when only an assembled user or system journey can prove the requirement.

Line coverage and raw test counts are supporting diagnostics, not primary quality goals.

## Public-core architecture

The canonical repository starts public. Public source code, schemas, generic profiles,
synthetic fixtures, examples, and architecture documentation may live here.

Private evidence remains in the target repository, Jenkins-controlled storage, or another
approved private evidence store and is represented to this platform only through sanitized,
bounded contracts.

## Planned package boundaries

- discovery: bounded repository/test-framework discovery
- inventory: normalized test inventory
- adapters: framework and executor integration adapters
- analysis: deterministic value, gap, flake, and policy analysis
- planning: deterministic ExecutionPlan compilation
- integration: the versioned Jenkins consumer contract (catalog, request
  compilation, outcome mapping, receipt ingestion, synthetic qualification)
- evidence: normalized QualityReceipt and evidence handling
- reporting: public-safe human and machine output

These boundaries are intentionally present before their implementation so later work does
not collapse policy, execution, and evidence into one coupled subsystem.


## Architecture decisions

The V1 authority and evidence decisions are locked in:

- docs/adr/0001-authority-model.md
- docs/testing-philosophy.md
- docs/evidence-layers.md
- docs/executor-boundaries.md

Later contract/schema work must encode these decisions rather than inventing a competing
authority model.
