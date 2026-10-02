"""Shared high-confidence secret-shape detection for every input ingress.

Both YAML contract parsing and JSON command input use this single
implementation, so a credential cannot be smuggled in through the ingress that
happens to have weaker checking.

The patterns are deliberately conservative: they target shapes that are
almost never legitimate in a public contract. This is a release guard, not a
replacement for provider secret scanning.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("github-fine-grained-token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("gitlab-token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    (
        "aws-access-key",
        re.compile(r"\b(?:AKIA|ASIA|AROA|AIDA|ANPA|ANVA|AIPA)[0-9A-Z]{16}\b"),
    ),
    ("private-key", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----")),
    (
        "bearer-token",
        re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._~+/-]{12,}"),
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"),
    ),
    (
        "credential-key-name",
        re.compile(
            r"(?i)\b(?:password|passwd|api[_-]?key|apikey|client[_-]?secret"
            r"|secret[_-]?key|access[_-]?token|auth[_-]?token)\b\s*[:=]\s*\S"
        ),
    ),
)


class SecretShapeError(ValueError):
    """Raised when an input value matches a forbidden secret shape."""


def find_secret_shape(value: str) -> str | None:
    """Return the rule name when a string matches a secret shape."""
    for rule, pattern in SECRET_PATTERNS:
        if pattern.search(value):
            return rule
    return None


def reject_secret_shapes(
    value: Any,
    *,
    source: str,
    error: type[Exception] = SecretShapeError,
) -> None:
    """Recursively reject any secret-shaped string in a parsed document.

    Raises ``error`` so each ingress reports through its own typed error while
    sharing one detection rule set.
    """
    if isinstance(value, str):
        rule = find_secret_shape(value)
        if rule is not None:
            raise error(f"{source}: value matches forbidden {rule} shape")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            reject_secret_shapes(key, source=source, error=error)
            reject_secret_shapes(child, source=source, error=error)
        return
    if isinstance(value, list):
        for child in value:
            reject_secret_shapes(child, source=source, error=error)