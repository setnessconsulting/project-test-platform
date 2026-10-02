# Adversarial Limits and Fail-Closed Behavior (API-396 Phase A)

This document is the operator-facing statement of what Test Platform bounds, and what
happens when a repository, executor, or result file exceeds those bounds. It describes
**implemented behavior**, not intended behavior.

Scope: the Phase A core. Jenkins/Portfolio Graph/portfolio-rollout integration
adversarial testing is API-399 and is explicitly out of scope here.

## Core invariants

| Invariant | Enforced in |
|---|---|
| The evaluator cannot convert `UNKNOWN`/`NOT_EVALUABLE` into `PASS` | `analysis/evaluator.py::_blocking_gap_result` |
| Provenance spoofing cannot widen authority | `evidence/receipts.py::validate_quality_receipt` |
| No unbounded recursion, traversal, memory, or output | `filesystem_safety.py`, `discovery/core.py`, `adapters/results.py`, `reporting` |
| Public-safe reports cannot leak secret or private data | `reporting/__init__.py`, `secret_shapes.py`, `public_safety.py` |
| Qualification evidence is bound to the exact Test Platform revision | `contracts.py::JenkinsExecutionRequest.platform_version` and `JenkinsReceiptSubmission.platform_version` |

## Deterministic limits

Every limit below is a hard bound. Exceeding one produces an error or an explicitly
degraded state — never a silent success.

### Repository traversal (`DiscoveryLimits`)

| Limit | Default | On exceed |
|---|---|---|
| `max_files` | 20,000 | `DiscoveryState.LIMIT_EXCEEDED`; inventory refuses to build |
| `max_depth` | 12 | `LIMIT_EXCEEDED` |
| `max_directories` | 20,000 | `LIMIT_EXCEEDED` |
| `max_entries` | 60,000 | `LIMIT_EXCEEDED` |
| `max_total_bytes` | 200 MB | `LIMIT_EXCEEDED` |
| `max_text_bytes` (per file) | 1 MB | file is not read |

Directory and entry bounds exist because a tree of empty directories contains no files
and would never trip a file cap. Traversal is bounded in depth explicitly rather than by
relying on a caught `RecursionError`.

Symlinks, Windows junctions, and other reparse points are rejected at every level
(`filesystem_safety.is_indirect`). `Path.is_symlink()` returns `False` for junctions, so
the platform additionally uses `os.path.isjunction` and the reparse-point file attribute.

### Result documents

| Limit | Default | On exceed |
|---|---|---|
| Result bytes | 2 MB | `ResultAdapterError` |
| Test cases | 10,000 | `ResultAdapterError` (enforced while iterating) |
| Test identity length | 1024 chars | `ResultAdapterError` |
| Message length | 4096 chars | truncated with `…[truncated]` |
| Duration | 0 – 86,400 s, finite | `ResultAdapterError` |

XML parsing uses an explicit parser policy that refuses any document type declaration,
so entity expansion and external-entity payloads fail during the parse rather than
depending on a substring pre-filter. The DTD substring check in `_bounded_xml` is a cheap
early exit, not the control.

### Aggregation semantics

- Any `FAIL` or `ERROR` fails a suite regardless of later retries.
- An empty suite, or one where every test was skipped, is `NOT_EVALUABLE` — never `PASS`.
- Only `PROVEN` is non-blocking. `MISSING` aggregates to `FAIL`; every other evidence
  state, including `NOT_APPLICABLE`, aggregates to `NOT_EVALUABLE`.

### Waivers

- Scope is `repo:<r>@profile:<id>:<version>@sha:<exact>` — bound to one revision, so a
  waiver granted at one commit cannot carry over to another.
- Wildcard scopes and duplicate waiver identifiers are rejected before evaluation begins.
- Only `MISSING` may be waived. `NOT_EVALUABLE` and `STALE` cannot.
- An expired waiver is ignored and the rejection is reported in the gap reason.
- Waivers never widen trust or evidence classes.

### Evidence freshness

Freshness is an identity check (`sha` plus profile binding) and, when a profile declares
`live_evidence_max_age_days`, an age check against that ceiling. A current-revision result
older than the declared ceiling degrades to `STALE`.

### Output

- JSON and Markdown rendering are bounded to 2 MB.
- JSON ingress is size-bounded and scanned for secret shapes, exactly like YAML ingress.

## Public-safe output

Redaction is **always applied**, not opt-in. `--public-safe` is retained for contract
compatibility and always reports `public_safe: true`.

Absolute paths are detected anywhere in a string, not only as a whole value, covering
Windows drive paths, UNC shares, extended-length (`\\?\`) paths, and POSIX absolute paths
under sensitive roots. Redacted path fragments become `<redacted-path>`; explicitly
sensitive field names become `<redacted>`.

Error messages embed only the file *name*, never a full host path, so a leak does not
depend on the redaction pattern being complete.

## Known boundaries (not closed in Phase A)

These are real and are not hidden:

- **The plan → request → receipt chain is unauthenticated.** `semantic_hash` is unkeyed
  SHA-256, and `execution_mode` (`CONTROLLER_EXECUTION`) and `evidence_origin` (`LIVE`) are
  **caller assertions, not attestations**. Anyone who can run
  `compile_jenkins_execution_request` locally can mint a submission that ingests as a
  live-qualification pass. Phase A closes forgery *within* the chain — receipt identity is
  recomputed, plan/SHA/profile/trust/evidence-classes are re-derived, and the platform
  revision is echoed and compared — but it cannot prove who produced the submission.
  Cryptographic attestation requires signing keys a public-safe repository must not hold
  and is an **API-399** dependency.
- **`--trust` and `--owner-approved` are self-asserted.** No ambient environment fact
  (CI ref, actor, branch protection) is consulted; the caller names its own trust class.
- **No persistent replay ledger.** `seen_receipt_ids` is caller-supplied. Receipt identity
  recomputation prevents re-stamping bypasses, but the platform keeps no durable record.
- **`--receipt-ids` on export are unverified.** They are operator-supplied strings folded
  into the export identity.
- **`contract.repositories` defaults to empty, which approves every repository** when a
  contract is constructed without it.
- **Windows junction tests may skip.** Symlink-based tests skip on Windows without
  developer mode, so CI can be green with zero symlink coverage on that host.

## Verification

```
python -m test_platform.verify
```

The adversarial suite is deterministic: seeded corpora in `tests/test_adversarial_core.py`
plus property tests in `tests/test_properties_adversarial.py` (hypothesis, `derandomize`),
so every result reproduces exactly from a clean checkout.