# Deterministic analysis model

API-381 through API-383 establish the first analysis layer. None of these analyses delete tests,
execute repository code, or use an LLM as canonical authority.

## Test value

Test-value classifications are advisory. The classifier consumes explicit evidence signals rather
than guessing from test names or source text.

Protection wins over cleanup signals. For example, a flaky test that uniquely protects a critical
security invariant remains REQUIRED and is separately identified as needing repair; flakiness does
not make the protected behavior disposable.

POSSIBLY_REDUNDANT means that equivalent declared-behavior evidence exists and no distinct failure
mode has been established. It is not permission to delete the test.

UNKNOWN is the correct result when deterministic evidence is insufficient.

## Behavior gaps

Behavior requirements are satisfied only by explicitly linked evidence of the required class.
Evidence is bound to an exact repository SHA and Quality Profile version.

Evidence from another SHA/profile is STALE. Missing evidence is MISSING. Evidence that was
attempted but cannot be evaluated is NOT_EVALUABLE. These states are never converted into PASS.

Critical journeys are evaluated separately under the subject identity
`journey:<journey-id>`. A journey requires its declared assembled evidence and all constituent
behaviors to be proven.

## History and flakiness

History groups equivalent executions by SHA, profile, suite, executor, and trust context. A FAIL or
ERROR and PASS in the same equivalent context is flaky. A retry PASS does not erase the earlier
failure.

Current freshness requires compatible evidence for the exact SHA/profile. Older evidence is STALE;
skipped-only current evidence is NOT_EVALUABLE.

The current history implementation is in-memory and deterministic. A later optional SQLite cache
may store history, but cache state is never canonical quality truth.
