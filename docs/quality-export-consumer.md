# QualityExport consumer mapping (for Portfolio Graph, API-393)

This document is the Test Platform side of the API-393 contract. It tells the
`project-portfolio-graph` consumer exactly how to interpret a versioned
`QualityExport` without parsing executor logs or reimplementing Test Platform
policy. The synthetic fixture at `fixtures/quality-export-example.json` is the
canonical round-trip example.

## Field mapping

| QualityExport field | Consumer meaning |
|---|---|
| `repository` | Repo identity; must match the portfolio registry entry exactly. |
| `profile.profile_id` / `profile.version` | Populates/validates the `QualityProfile` relationship. A version the consumer was not qualified against fails closed. |
| `sha` | Qualified exact SHA. Evidence for any other SHA is drift, not qualification. |
| `result` | `pass` / `fail` / `not-evaluable` / `blocked`. Only `pass` can support maintenance readiness. |
| `required_behaviors`, `proven_behaviors`, `not_evaluable_behaviors` | Behavior counts for readiness thresholds. `required != proven + waived` accounting must reconcile; anything else is drift. |
| `critical_journeys_*` | Assembled-journey evidence state; a `pass` with unproven critical journeys must not read as ready. |
| `receipt_ids` | Opaque receipt references for audit join. Never fetch or parse raw executor output through them. |
| `generated_at` | Freshness input only; excluded from semantic identity. |
| `export_id` | Deduplication key. Same semantic payload reproduces the same ID. |
| `schema_version` | Unsupported major version fails closed. |

## Drift rules (all fail closed)

- Export `sha` differs from the registry HEAD under review → stale; not evidence.
- Export `profile` differs from the repository binding → mismatch; not evidence.
- Partial export (missing behavior/journey subjects) → `not-evaluable`; never `pass`.
- Unknown `schema_version` → reject; never guess.

## Non-goals

The consumer must not parse Jenkins/GitHub logs, infer Test Platform policy,
mutate quality state, or execute tests. Those authorities stay where they are.
