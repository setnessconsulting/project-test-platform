# Deterministic AI-agent testing guidance

The guide surface helps Codex, Freebuff, CommandCode, and other coding agents choose the smallest
meaningful verification change. It is not an AI quality gate.

## Trusted inputs

Guidance is compiled only from:

- the validated repository manifest and exact Quality Profile version;
- repository behavior and critical-journey declarations;
- an exact-repository/SHA TestInventory;
- affected behavior IDs supplied by trusted change context;
- complete GapFinding state for every affected behavior and journey.

Unknown affected behavior IDs or incomplete affected gap state fail closed.

## Guidance contents

The V1 guidance document contains:

- repository/SHA and exact profile binding;
- affected behavior IDs;
- required and conditional evidence classes;
- existing relevant behavior-linked tests;
- relevant evidence IDs and gap state;
- affected critical journeys;
- declared suites capable of producing the required evidence;
- whether a new test appears necessary from deterministic evidence coverage;
- bounded next actions;
- fixed anti-pattern guidance.

A changed behavior that participates in a critical journey inherits that journey's assembled
evidence obligation, including end-to-end evidence.

If current behavior and journey findings are already PROVEN for the exact SHA/profile, guidance
explicitly says that no new test is required. Missing evidence does not automatically mean "add a
test": when an existing relevant test already provides the required evidence class, guidance
prefers repairing/extending/re-running that test before creating overlapping coverage.

STALE evidence asks for exact-SHA re-execution. NOT_EVALUABLE evidence asks the operator/agent to
restore evaluability first.

## Safety boundaries

Guidance never:

- authorizes automatic test deletion;
- treats advisory redundancy as permission to remove a test;
- widens executor trust;
- requests credentials;
- substitutes E2E-only coverage for focused lower-layer evidence;
- invents behavior relationships from filenames or model inference;
- imports unrelated private portfolio context.

Consumers may use an LLM to explain or implement the guidance, but canonical facts and required
evidence remain deterministic Test Platform outputs.
