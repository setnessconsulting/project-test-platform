# Testing philosophy

## Primary rule

Use the lowest-cost test layer that truthfully proves the behavior.

Require assembled end-to-end evidence when only an assembled user or system journey can
prove the requirement.

## What this rejects

The platform does not treat any of these as a quality objective by itself:

- raw test count;
- line coverage percentage;
- the number of end-to-end tests;
- the number of unit tests;
- framework-specific snapshot volume.

Unit tests are not lower quality by definition. End-to-end tests are not higher quality by
definition.

## Examples

A deterministic policy test is the right layer when proving that an approval cannot be
reused for a different target.

A contract test is the right layer when proving that a provider's partial response is
normalized into PARTIAL coverage.

An integration test is appropriate when proving that authorization, persistence, and a
service boundary work together.

An end-to-end test is required when a critical user journey can only be proven through the
assembled application.

## Test additions

Agents and developers should add the smallest set of tests that satisfies the affected
declared behavior requirements. Duplicating the same behavior at multiple layers requires a
distinct failure-mode justification.

## Test removal

Test-value analysis is advisory. The platform does not automatically delete, disable, or
rewrite tests. A regression/security test can remain required even when a higher-level test
also touches the same feature if it protects a distinct failure mode.
