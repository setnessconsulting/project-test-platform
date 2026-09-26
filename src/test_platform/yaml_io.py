"""Safe bounded YAML parsing helpers for public contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import yaml

from test_platform.public_safety import SECRET_PATTERNS


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
    _reject_secret_shapes(data, source=source)
    return data


def _reject_secret_shapes(value: Any, *, source: str) -> None:
    if isinstance(value, str):
        for rule, pattern in SECRET_PATTERNS:
            if pattern.search(value):
                raise YamlContractError(f"{source}: value matches forbidden {rule} shape")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_secret_shapes(key, source=source)
            _reject_secret_shapes(child, source=source)
        return
    if isinstance(value, list):
        for child in value:
            _reject_secret_shapes(child, source=source)
