# Contract versioning

## V1 compatibility rule

Every public top-level contract carries schema_version 1 or is referenced from a V1
top-level contract.

Consumers must reject unsupported major schema versions. A producer may add a new optional
field only through an explicitly reviewed schema evolution that remains compatible with the
declared version policy. Unknown fields are currently rejected by the strict V1 models and
schemas so silent authority expansion cannot occur.

## Schema source

The Python models in test_platform.contracts are the typed implementation authority for the
current repository revision. The checked-in language-neutral bundle at
schemas/v1/contracts.schema.json is generated from those models.

Canonical verification fails if the checked-in bundle and generated contracts diverge.

## Semantic identity

Canonical JSON sorts object keys and uses stable separators.

Some envelope timestamps describe when an otherwise identical artifact was emitted. Models
that require stable semantic identity explicitly exclude only those named envelope fields
from semantic_payload. Timestamp fields that change meaning, such as waiver creation or
expiry, remain part of semantic content.

Do not globally strip timestamp fields.

## Breaking changes

A breaking change requires:
- a new major schema version;
- an explicit migration/compatibility decision;
- consumer qualification for Jenkins, Portfolio Graph, and agent-facing integrations where
  applicable;
- preservation of old-version rejection semantics until the migration is complete.

## API-401 deployment-placement evolution (V1 pre-release)

API-401 adds `move-deployment-to-jenkins` to `WorkflowPlacement` and records explicit
deployment-migration prerequisites on workflow observations. The legacy `retain-deployment`
value remains in the schema for reading historical evidence but is never emitted by the
current classifier. This is an explicitly reviewed pre-release correction under the
owner-approved portfolio end state (routine CI and deployment execution move to Jenkins);
it does not bump the V1 major version because V1 has not yet released under API-397 and no
qualified consumer has been released against the stale retention policy.
