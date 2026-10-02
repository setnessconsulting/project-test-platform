"""Safe bounded YAML parsing helpers for public contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import yaml

from test_platform.secret_shapes import reject_secret_shapes


class YamlContractError(ValueError):
    """Raised when a bounded YAML contract cannot be safely parsed."""


def parse_yaml_mapping(text: str, *, source: str) -> dict[str, Any]:
    """Parse YAML with safe_load and require one mapping document."""
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise YamlContractError(f"{source}: invalid YAML") from exc
    if not isinstance(value, Mapping):
        raise YamlContractError(f"{source}: expected a mapping document")
    data = dict(value)
    reject_secret_shapes(data, source=source, error=YamlContractError)
    return data
