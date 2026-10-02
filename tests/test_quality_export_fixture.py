"""Synthetic QualityExport fixture round-trip (API-393 consumer enabler).

The checked-in fixture is the canonical synthetic example Portfolio Graph
consumers validate against. It must always parse as a valid QualityExport and
preserve the invariants the consumer contract depends on.
"""

from __future__ import annotations

import json
from pathlib import Path

from test_platform.contracts import QualityExport, QualityResult


def test_synthetic_export_fixture_round_trips() -> None:
    raw = json.loads(
        Path("fixtures/quality-export-example.json").read_text(encoding="utf-8")
    )
    export = QualityExport.model_validate(raw)

    assert export.schema_version == "1"
    assert export.result is QualityResult.PASS
    assert len(export.sha) == 40
    assert export.profile.profile_id == "python-control-plane-v1"
    assert export.required_behaviors == export.proven_behaviors
    assert export.not_evaluable_behaviors == 0
    assert export.receipt_ids == ("receipt:synthetic-1",)

    # Semantic identity excludes only the envelope timestamp: re-serializing
    # the same payload must reproduce the same export ID.
    assert (
        QualityExport.model_validate(export.model_dump(mode="json")).export_id
        == export.export_id
    )
