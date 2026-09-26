"""Critical behavior and journey declaration loading."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from test_platform.contracts import BehaviorDocument
from test_platform.yaml_io import YamlContractError, parse_yaml_mapping

MAX_BEHAVIOR_BYTES = 512 * 1024


class BehaviorDeclarationError(ValueError):
    """Raised when behavior/journey declarations are unsafe or invalid."""


def load_behavior_document(path: Path) -> BehaviorDocument:
    """Load one bounded behavior declaration document."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise BehaviorDeclarationError(f"cannot read behavior document: {path}") from exc
    if size > MAX_BEHAVIOR_BYTES:
        raise BehaviorDeclarationError("behavior document exceeds maximum size")

    try:
        data = parse_yaml_mapping(path.read_text(encoding="utf-8"), source=str(path))
        return BehaviorDocument.model_validate(data)
    except (OSError, ValidationError, YamlContractError) as exc:
        raise BehaviorDeclarationError(f"invalid behavior document: {path}") from exc
