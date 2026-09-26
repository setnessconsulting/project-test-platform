# V1 JSON Schema bundle

contracts.schema.json is the checked-in language-neutral schema bundle generated from the
strict public V1 models in src/test_platform/contracts.py.

The x-contract-fragments map identifies the JSON Pointer fragment for each public contract
model. Consumers should validate against the specific fragment they expect rather than
treating the bundle root as a generic payload schema.

Run:

    python -m test_platform.schema_registry --check

to verify that the checked-in bundle still matches the Python contract models.
