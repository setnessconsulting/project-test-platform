# Python 3.12 Jenkins shadow cohort

## Scope

This cohort covers only `setnessconsulting/project-test-platform` and its single
Linux `verify` workflow in `.github/workflows/verify.yml`. The exact Test
Platform binding is `python-control-plane-v1@1.0.0`; the declared suite is
`verify` with `pr-untrusted` trust. The suite uses the existing repository
verification commands:

1. `python -m pip install -e ".[dev]"`
2. `python -m test_platform.verify`

The Jenkins portfolio dispatcher selects the centrally managed
`python312-test-platform-v1` implementation. It pins Python `3.12.14`, runs on
the one-build `setness-python312-ephemeral` agent, and publishes the
`jenkins-pr-gate` check. The agent and command vector are controller-owned; the
manifest declares only the symbolic `verify` entrypoint and evidence classes.

This cohort uses the portfolio PR dispatcher, not the separate API-390
Test Platform contract pipeline. The API-390 catalog and its `test-platform`
pipeline are a different integration route and do not establish this profile's
Python 3.12 execution result.

## Trust and fallback

- Run only against a current, non-draft pull request in this repository authored
  by `setnessconsulting`. Do not dispatch fork or outside-author pull requests.
- Bind every Jenkins result to the controller-verified current PR head SHA. A
  stale or mismatched checkout is not evidence for that head.
- Treat pull request code as untrusted. The disposable agent receives no
  provider, deployment, or production credentials; checkout credentials are
  removed before repository commands run, and the workspace is cleaned after
  execution.
- Keep GitHub Actions `verify` enabled and authoritative during this shadow.
  The owner-controlled `workflow_dispatch` path remains the same-SHA fallback.
  This cohort does not change required checks, workflow triggers, deployment
  jobs, or fork policy.

## Minimal distinct-outcome evidence

The bounded evidence set records outcomes by exact repository, PR number, head
SHA, check source/App, result, duration, and cleanup status. One passing result
alone is insufficient to show failure visibility.

| Case | Exact-head evidence | Expected Jenkins result |
| --- | --- | --- |
| Standard verification | Jenkins and Actions both run the same owner-authored PR head | `success` |
| Deliberate verification failure | Both systems run the same controlled failing head | `failure`; no pass receipt |
| Executor unavailable, timeout, cancellation, or stale head | Record the normalized check result and observed SHA | Visible failure or blocked/not-evaluable result; never `success` |

The approved one-profile observation waiver applies only to this bounded cohort;
it does not waive distinct outcome coverage, exact-SHA/App attribution, cleanup,
fallback, or the separate cutover gates. Record each case as pending until its
live Jenkins check and same-SHA Actions evidence are read back. Synthetic
adapter fixtures remain synthetic evidence and cannot fill a live-check row.

## Qualification state

This file describes the candidate lane and its evidence contract. It does not
claim that Jenkins is authoritative or that any live Jenkins outcome has
passed. Keep Actions as the required verification path until the owner-approved
qualification and no-gap cutover gates are complete.
