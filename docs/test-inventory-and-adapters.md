# Test inventory and result adapters

## Inventory

API-379 builds a deterministic inventory only from bounded discovery evidence. It never executes
repository tests and never infers behavior relationships from file or test names.

A test identity is currently path-level and namespaced by framework:

    <framework>:<repository-relative-path>

Behavior links are explicit inputs supplied by repository-owned declarations or later traceability
work. Unknown links remain diagnostics.

A repository path detected by more than one framework is kept as separate framework identities and
reported as ambiguous. Test Platform does not guess which framework owns the file.

MALFORMED or LIMIT_EXCEEDED discovery cannot be converted into a complete TestInventory. UNKNOWN
discovery can produce an empty inventory, but that means only that no supported framework was
discovered; it is not qualification evidence.

## Framework result adapters

API-380 normalizes result interchange without replacing pytest, Jest, Vitest, Playwright, Pester,
or their runners.

V1 supports:

- pytest via JUnit XML;
- Jest via JUnit XML;
- Vitest via JUnit XML;
- Playwright via JUnit XML;
- Pester via JUnit XML or NUnit-style XML;
- generic JUnit XML parsing through the common parser.

Result parsing is bounded by document size and test-case count. DTD/entity declarations are
rejected before parsing. Result files are data and are never executed.

Retries are preserved as attempts. A later passing retry does not erase an earlier failure; this is
required by the flake/history work in API-383.

Framework adapters normalize evidence. They do not decide whether a test is valuable, whether a
behavior is proven, or whether a repository is qualified.
