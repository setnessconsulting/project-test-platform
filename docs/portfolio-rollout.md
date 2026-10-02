# Portfolio rollout runbook (API-398)

Repeatable per-repository path from unbound to Jenkins-authoritative. Do the
repositories one at a time; never flip a global switch.

## Per-repository sequence

1. **Inventory.** Record the repo's tests, CI workflows, and deployment surface.
   Baseline hosted verification vs deployment minutes separately.
2. **Bind.** Open a PR adding `.test-platform.yaml` (explicit profile, version
   range, behavior path, suites) plus `quality/behaviors.yaml` (critical
   behaviors/journeys with required evidence classes). New files only; no CI
   changes in this PR.
3. **Assess.** Run offline from the repo root:
   `test-platform validate`, `inventory`, `gaps`, `plan`, `evaluate`,
   `actions` / `migration-plan` (with observed workflow inputs),
   `portfolio-export`. Keep evidence in the target repo or Jenkins-controlled
   storage — never in the public Test Platform repo.
4. **Shadow.** With CONSULTING-355 GO, run the same exact PR-head SHA through
   authoritative checks and the Test Platform/Jenkins plan. Cover green,
   deliberate failure, stale-head/cancellation, outage/fallback, and
   provenance cases. Zero unexplained divergence.
5. **Cutover.** Only after API-395 PASS for the locked pilot pattern and the
   owner-approved no-gap transition: require the Jenkins check in branch
   protection, then disable routine GitHub-hosted verification/deployment.
6. **Read back.** Confirm Portfolio Graph/Test Platform evidence reflects the
   migrated state and the exact SHA.

## Safety invariants

- No routine Actions gate is disabled before same-SHA parity + fallback +
  rollback proof for that repository.
- A repo counts as migrated only on live exact-SHA evidence, never on config
  existing in Git.
- Frozen/rollback-audit repos are out of scope unless a bounded maintenance
  issue (e.g. API-400) says otherwise.
- Reconcile the active-repo inventory immediately before closeout so
  added/removed repos cannot escape the gate.
