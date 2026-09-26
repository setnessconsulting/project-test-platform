# Executor boundaries

## Test Platform

Test Platform compiles deterministic ExecutionPlans and evaluates normalized QualityReceipts.
It does not run a Jenkins controller, own provider credentials, deploy applications, or
schedule background work.

## Jenkins

Project Jenkins owns controller configuration, build agents, credentials, job isolation,
GitHub Check publication, recovery, and fallback.

A target pull request must not supply trusted Jenkins controller logic.

## Local execution

Developers and agents may run repository-defined suites locally when permitted by the
manifest and trust policy. Local success is repository evidence; it is not automatically
live qualification evidence.

## GitHub Actions

GitHub Actions remains appropriate for deliberately retained GitHub-native, security,
clean-room, fallback, or deployment work. Test Platform can recommend placement but cannot
disable workflows.

## Provider systems

Provider access remains with provider-specific control planes. A repository manifest or test
output cannot select provider credentials, accounts, permissions, or mutation policy.

## Portfolio Graph

Portfolio Graph consumes the versioned sanitized quality export. It does not consume raw
Jenkins logs and does not reinterpret Test Platform quality rules.
