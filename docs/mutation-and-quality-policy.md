# Mutation evidence and quality-policy evaluation

## Selective mutation/fault evidence

Mutation analysis is profile-driven. A repository whose profile marks mutation analysis
not-applicable does not acquire a mutation gate merely because a tool can run mutations.

Applicable mutation/fault trials are bounded by trial count and total duration. Surviving trials
produce an evidence gap. Timeout/error evidence is NOT_EVALUABLE. The platform does not
automatically create tests or edit source code from a surviving mutation.

The intended targets are deterministic high-value logic such as authorization policy, validation,
state machines, scoring, and business calculations—not every UI component or browser journey.

## Quality evaluation

The evaluator has no numerical quality score. It combines explicit current profile-rule states and
behavior-gap findings using deterministic precedence:

- explicit execution/environment blocker -> BLOCKED;
- stale or not-evaluable mandatory evidence -> NOT_EVALUABLE;
- missing mandatory evidence -> FAIL;
- otherwise -> PASS.

Informational and non-applicable profile requirements do not gate quality. Conditional
requirements gate only when a trusted caller marks their rule ID applicable.

## Waivers

A V1 waiver must bind exactly to:

    repo:<repository>@profile:<profile-id>:<profile-version>

Wildcard scopes are prohibited. A waiver can apply only to MISSING evidence for a rule that the
profile marks waivable. It cannot turn STALE or NOT_EVALUABLE evidence into PASS and cannot waive a
non-waivable criterion.

Profile version changes naturally invalidate prior waiver scope. Expired waivers stop applying.
Every applied waiver remains visible in the QualityAssessment.

These semantics prevent an exception from becoming a generic policy bypass.
