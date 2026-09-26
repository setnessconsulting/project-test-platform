# Evidence layers

V1 recognizes the following evidence classes.

## Static

Lint, type checking, schema validation, compilation, packaging, and other checks that prove
structural properties without executing the full behavior.

## Deterministic / unit

Small deterministic tests of algorithms, invariants, validation, authorization, calculations,
state machines, or other behavior that can be proven faithfully in isolation.

## Contract

Tests of an interface boundary such as a provider adapter, schema, protocol, or consumer
contract.

## Integration

Tests that prove multiple real components work together without requiring the complete
user-facing system.

## End-to-end

Tests that prove an assembled user or system journey. Critical journeys require E2E when
their requirement cannot be established by a lower-cost layer.

## Adversarial / security

Negative and abuse-path evidence for trust, authorization, injection, stale-target,
redaction, isolation, and failure semantics.

## Live qualification

Bounded evidence against a real provider or environment. Live qualification is distinct
from fixture or synthetic evidence and uses a trusted execution class.

## Performance

Evidence against an explicit latency, throughput, resource, or duration budget.

## Manual / owner gate

Evidence that cannot or should not be automated, including explicit owner approval or a
human assessment when the policy declares it.

## Evidence selection

A Quality Profile declares which classes are required, conditional, informational, or
not applicable. Repository names, GitHub owners, languages, frameworks, and AI output do not
silently change evidence requirements.
