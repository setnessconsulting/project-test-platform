"""Deterministic JSON serialization and semantic hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Serialize a JSON-compatible value deterministically."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def semantic_hash(value: Any) -> str:
    """Return a stable SHA-256 over canonical semantic content."""
    encoded = canonical_json(value).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
