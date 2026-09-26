# Quality Profiles

Quality Profiles are versioned, explicit policy bundles. A target repository selects one in
its .test-platform.yaml manifest. Test Platform never infers a profile from repository owner,
name, language, framework, or AI output.

V1 ships eight profiles:

- python-control-plane-v1
- typescript-control-plane-v1
- web-application-v1
- browser-game-v1
- static-site-v1
- local-agent-v1
- infrastructure-tool-v1
- documentation-tool-v1

Each profile declares required, conditional, informational, or not-applicable evidence,
allowed execution trust classes, recommended execution targets, live-evidence freshness
where applicable, critical-journey E2E policy, and mutation-analysis applicability.

A profile rule marked non_waivable cannot be bypassed by a repository-local exception.

Profile versions are exact in the V1 manifest contract. A future compatible-range mechanism
requires a reviewed contract change rather than implicit semantic-version interpretation.
