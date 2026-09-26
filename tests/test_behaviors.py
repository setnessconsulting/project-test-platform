from __future__ import annotations

from pathlib import Path

import pytest

from test_platform.behaviors import BehaviorDeclarationError, load_behavior_document


@pytest.mark.parametrize(
    "example",
    [
        "python-control-plane",
        "web-application",
        "browser-game",
        "infrastructure-tool",
    ],
)
def test_example_behavior_documents_validate(example: str) -> None:
    document = load_behavior_document(Path("examples") / example / "quality" / "behaviors.yaml")

    assert document.behaviors


def test_duplicate_behavior_ids_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "behaviors.yaml"
    path.write_text(
        """
schema_version: "1"
behaviors:
  - behavior_id: duplicate
    description: one
    criticality: high
    required_evidence: [deterministic]
  - behavior_id: duplicate
    description: two
    criticality: high
    required_evidence: [deterministic]
""",
        encoding="utf-8",
    )

    with pytest.raises(BehaviorDeclarationError, match="invalid behavior document"):
        load_behavior_document(path)


def test_unknown_journey_behavior_reference_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "behaviors.yaml"
    path.write_text(
        """
schema_version: "1"
behaviors:
  - behavior_id: known
    description: known behavior
    criticality: critical
    required_evidence: [end-to-end]
critical_journeys:
  - journey_id: broken
    description: references missing behavior
    behavior_ids: [missing]
    required_evidence: [end-to-end]
""",
        encoding="utf-8",
    )

    with pytest.raises(BehaviorDeclarationError, match="invalid behavior document"):
        load_behavior_document(path)


def test_critical_journey_requires_e2e(tmp_path: Path) -> None:
    path = tmp_path / "behaviors.yaml"
    path.write_text(
        """
schema_version: "1"
behaviors:
  - behavior_id: core
    description: core behavior
    criticality: critical
    required_evidence: [integration]
critical_journeys:
  - journey_id: core-flow
    description: core flow
    behavior_ids: [core]
    required_evidence: [integration]
""",
        encoding="utf-8",
    )

    with pytest.raises(BehaviorDeclarationError, match="invalid behavior document"):
        load_behavior_document(path)
