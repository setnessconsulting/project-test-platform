# Security

## Public repository rule

Treat every committed byte as permanently public. Making this repository private later does
not retract clones, forks, screenshots, cached copies, or previously distributed history.

Never commit:

- credentials, API keys, tokens, passwords, or private keys;
- private repository inventories or proprietary source/test output;
- raw private Jenkins logs;
- internal user-specific machine paths;
- customer or learner data;
- production fixtures or vulnerability findings tied to private systems;
- raw private qualification evidence.

## Trust boundaries

Repository files, manifests, test names, test output, pull-request content, result files,
and executor output are untrusted data. They must not be allowed to choose credentials,
expand authority, mutate policy, or configure trusted Jenkins controller behavior.

## Phase A adversarial invariants

These are enforced in code and covered by the adversarial suite:

- **The evaluator cannot produce `PASS` from non-proven evidence.** Only `PROVEN` is
  non-blocking. `MISSING` aggregates to `FAIL`; `NOT_EVALUABLE`, `STALE`, and
  `NOT_APPLICABLE` all aggregate to `NOT_EVALUABLE`. A repository cannot assert
  `NOT_APPLICABLE` for its own required evidence classes to make a gap disappear.
- **Behavior-gap analysis is an explicit input.** Omitting it yields `NOT_EVALUABLE`, not
  `PASS`, so an unevaluated repository is never reported as proven.
- **A receipt cannot carry a forged identity.** The semantic identity is recomputed from
  the receipt's own content on validation, so re-stamping byte-identical content with a
  fresh identifier no longer bypasses the replay ledger.
- **Evidence classes are bound to the suite that produced them.** A receipt citing an
  evidence class its suite never declared is refused.
- **Evidence is bound to an exact revision.** Every revision-bound contract requires a
  full 40–64 character lowercase hexadecimal SHA; a short, non-hex, or traversal-shaped
  identifier is rejected. Waivers are bound to the exact revision as well.
- **Traversal and resource use are bounded.** Repository walks are bounded in depth,
  directories, entries, files, and bytes, and never follow symlinks, junctions, or reparse
  points. Result documents are bounded in bytes, case count, identity length, message
  length, and duration. See `docs/adversarial-limits.md`.
- **Public output is always redacted.** Absolute paths are detected anywhere in a string —
  Windows drive, UNC, extended-length, and POSIX forms — and redaction is applied
  unconditionally rather than behind a flag.

## Known boundaries (API-399)

The plan → request → receipt chain is **not cryptographically authenticated**. `semantic_hash`
is unkeyed SHA-256, and `execution_mode: CONTROLLER_EXECUTION` and `evidence_origin: LIVE`
are **caller assertions, not attestations**. Phase A closes forgery within the chain and
binds evidence to the Test Platform revision that minted it, but cannot prove who produced a
submission. Real attestation is an API-399 dependency. `--trust` and `--owner-approved` are
likewise self-asserted, and the platform keeps no persistent replay ledger. These limitations
are enumerated in `docs/adversarial-limits.md`.

## Jenkins consumer contract invariants

The Jenkins consumer contract fails closed on: repository mismatch, SHA mismatch, plan
identity mismatch, unsupported plan or receipt schema versions, trust escalation, unapproved
executors, suites, entrypoints, capabilities, or evidence classes, oversized artifact or
evidence declarations, stale-head execution presented as current-head evidence, and
evidence minted under a different Test Platform revision. The
normalized result table is owned by Test Platform and shipped inside every request, so an
executor or agent failure can never be turned into a pass. Receipt identity is re-derived
by Test Platform on ingestion, so a forged or replayed receipt fails. Synthetic fixture
evidence is always labelled synthetic and can never be mistaken for live qualification.

## Secret and path scanning

The repository includes a deterministic public-safety scanner covering high-confidence
secret shapes (GitHub classic and fine-grained tokens, GitLab PATs, AWS access keys across
all key prefixes, PEM private keys of any algorithm, bearer authorization headers, JWTs,
and credential-shaped key names) plus private user paths. It is a release guard, not a
replacement for provider secret scanning or code review. The scanner's own traversal is
bounded and non-following, and a repository that exceeds its bounds is reported rather than
partially scanned as clean.

## Reporting vulnerabilities

Do not open a public issue containing an exploitable vulnerability, credential, private
repository detail, or customer data. Use the repository owner's private security/reporting
channel instead.
