# Stable CLI and output contract

The V1 CLI is an offline-first operator and agent interface over deterministic Test Platform
contracts. Canonical commands do not require an AI model.

## Commands

- validate: validate the repository manifest, exact Quality Profile binding, and behaviors.
- inventory: run bounded static framework discovery and normalized inventory construction.
- behaviors: render declared behaviors and critical journeys.
- audit: combine validation, discovery, and inventory without inventing execution evidence.
- gaps: evaluate behavior/journey evidence observations for an exact SHA/profile.
- plan: compile an exact-SHA ExecutionPlan from validated policy inputs.
- evaluate: apply deterministic quality policy to explicit rule/gap/waiver state.
- actions: classify sanitized GitHub Actions observations by execution placement.
- migration-plan: render only safe migration candidates; it never mutates workflows.
- report: combine repository context/inventory with an optional QualityAssessment.
- portfolio-export: build a complete versioned QualityExport for Portfolio Graph.
- guide: generate deterministic behavior-focused AI-agent testing guidance.
- doctor: run bounded credential-free environment diagnostics.

## Output contract

Every JSON command result uses this envelope:

    {
      "schema_version": "1",
      "tool_version": "...",
      "command": "...",
      "public_safe": false,
      "payload": {...}
    }

JSON uses deterministic key ordering. Human output is concise Markdown and explicitly identifies
itself as a summary; complete evidence remains available through JSON.

Evidence-dependent commands require the repository identity and exact SHA where applicable.
Evaluation requires an explicit ISO-8601 time so waiver expiry does not depend on an implicit
wall-clock value.

Invalid manifest/profile/input data exits non-zero with a bounded error instead of a traceback.

## Offline and public-safe operation

Repository commands consume checked-in declarations plus explicit bounded JSON inputs. They do
not fetch credentials or provider state.

The --public-safe output mode redacts absolute paths and explicitly sensitive field names before
serialization. Canonical command payloads do not carry raw logs or credential values.

Input and output documents have hard byte limits. Partial Portfolio Graph exports fail closed:
every declared behavior and critical journey must have an explicit evidence finding before a
QualityExport can be generated.

## Gate exit behavior

Analysis commands return success when analysis completed, even if findings are missing or stale.
The evaluate command is a gate: PASS returns zero; FAIL, NOT_EVALUABLE, and BLOCKED return one.
Malformed or incompatible input returns two.
