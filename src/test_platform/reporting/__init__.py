"""Bounded machine-readable and human-readable reporting helpers."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from test_platform import __version__
from test_platform.canonical import semantic_hash
from test_platform.contracts import (
    BehaviorDocument,
    EvidenceState,
    QualityAssessment,
    QualityExport,
)
from test_platform.secret_shapes import reject_secret_shapes

MAX_JSON_INPUT_BYTES = 2_000_000
MAX_OUTPUT_BYTES = 2_000_000

# Matched anywhere in a string, not only at the start. Real output embeds a
# host path inside a longer message ("invalid repository manifest: C:\Users\"),
# so a whole-value test would leave the operator's home path in the output.
_WINDOWS_ABSOLUTE = re.compile(r"(?i)\b[a-z]:[\\/]")
_UNC_ABSOLUTE = re.compile(r"\\\\[a-z0-9._$-]+\\")
_POSIX_ABSOLUTE = re.compile(
    r"(?<![A-Za-z0-9_])/(?:home|Users|root|var|tmp|etc|opt|private|mnt|srv)/"
)
_EXTENDED_WINDOWS = re.compile(r"\\\\\?\\")

_PRIVATE_FIELD_MARKERS = (
    "credential",
    "password",
    "private_path",
    "raw_log",
    "secret",
    "token",
)


class ReportingError(ValueError):
    """Raised when bounded reporting cannot safely produce an output."""


def load_json_file(path: Path, *, max_bytes: int = MAX_JSON_INPUT_BYTES) -> Any:
    """Load one bounded UTF-8 JSON file.

    JSON ingress is scanned for secret shapes exactly like YAML ingress, so a
    credential cannot be smuggled in through a command input file.
    """
    try:
        size = path.stat().st_size
    except OSError as exc:
        # Name only: a host path here would be printed to stderr.
        raise ReportingError(f"cannot read JSON input: {path.name}") from exc
    if size > max_bytes:
        raise ReportingError(f"JSON input exceeds {max_bytes} bytes")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ReportingError(f"invalid JSON input: {path.name}") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReportingError(f"invalid JSON input: {path.name}") from exc
    reject_secret_shapes(value, source=path.name, error=ReportingError)
    return value


def _looks_absolute_path(value: str) -> bool:
    return bool(
        _WINDOWS_ABSOLUTE.search(value)
        or _UNC_ABSOLUTE.search(value)
        or _EXTENDED_WINDOWS.search(value)
        or _POSIX_ABSOLUTE.search(value)
    )


def _redact_embedded(value: str) -> str:
    """Replace an absolute path inside a longer message with a marker.

    Whole-string replacement would discard surrounding context operators need;
    only the path-bearing portion is replaced.
    """
    for pattern in (
        _WINDOWS_ABSOLUTE,
        _UNC_ABSOLUTE,
        _EXTENDED_WINDOWS,
        _POSIX_ABSOLUTE,
    ):
        value = pattern.sub("<redacted-path>", value)
    return value


def public_safe_value(value: Any, *, key: str | None = None) -> Any:
    """Redact private-path and explicitly sensitive fields from structured output.

    Applied unconditionally to every command envelope. Public output is
    permanently public, so redaction is not opt-in: ``--public-safe`` remains
    for contract compatibility and is always enforced.
    """
    normalized_key = (key or "").lower().replace("-", "_")
    if any(marker in normalized_key for marker in _PRIVATE_FIELD_MARKERS):
        return "<redacted>"

    if isinstance(value, str):
        return (
            "<redacted-path>"
            if _looks_absolute_path(value)
            else _redact_embedded(value)
        )
    if isinstance(value, dict):
        return {
            str(item_key): public_safe_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [public_safe_value(item) for item in value]
    return value


def command_envelope(
    command: str,
    payload: dict[str, Any],
    *,
    public_safe: bool = True,
) -> dict[str, Any]:
    """Wrap a command result in the stable V1 output envelope.

    Redaction is always applied. ``public_safe`` is retained for contract
    compatibility with existing consumers but is no longer a switch: output is
    public-safe whether or not it was requested.
    """
    return {
        "schema_version": "1",
        "tool_version": __version__,
        "command": command,
        "public_safe": True,
        "payload": public_safe_value(payload),
    }


def serialize_json(value: Any) -> str:
    """Serialize bounded deterministic JSON."""
    rendered = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    if len(rendered.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ReportingError("rendered output exceeds maximum size")
    return rendered


def render_markdown(command: str, payload: dict[str, Any]) -> str:
    """Render a concise deterministic Markdown view with explicit summary semantics."""
    lines = [f"# Test Platform: {command}", ""]
    for key in sorted(payload):
        value = payload[key]
        label = key.replace("_", " ")
        if isinstance(value, (str, int, float, bool)) or value is None:
            lines.append(f"- **{label}**: {value}")
        elif isinstance(value, (list, tuple)):
            lines.append(f"- **{label}**: {len(value)} item(s)")
        elif isinstance(value, dict):
            lines.append(f"- **{label}**: {len(value)} field(s)")
        else:
            lines.append(f"- **{label}**: {type(value).__name__}")
    lines.extend(
        [
            "",
            "_This is the bounded human summary. Use --json for the complete "
            "machine-readable payload._",
        ]
    )
    rendered = "\n".join(lines) + "\n"
    if len(rendered.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ReportingError("rendered output exceeds maximum size")
    return rendered


def build_quality_export(
    assessment: QualityAssessment,
    behaviors: BehaviorDocument,
    *,
    receipt_ids: tuple[str, ...],
    generated_at: datetime,
) -> QualityExport:
    """Build a complete portfolio-safe quality export from full behavior findings."""
    findings = {item.behavior_id: item for item in assessment.gaps}
    expected_behaviors = {item.behavior_id for item in behaviors.behaviors}
    expected_journeys = {
        f"journey:{item.journey_id}"
        for item in behaviors.critical_journeys
    }
    missing_subjects = (expected_behaviors | expected_journeys) - set(findings)
    if missing_subjects:
        raise ReportingError(
            "quality export requires complete behavior/journey findings; missing: "
            + ", ".join(sorted(missing_subjects))
        )

    not_evaluable_states = {
        EvidenceState.NOT_EVALUABLE,
        EvidenceState.STALE,
    }
    proven_behaviors = sum(
        findings[item].state is EvidenceState.PROVEN
        for item in expected_behaviors
    )
    not_evaluable_behaviors = sum(
        findings[item].state in not_evaluable_states
        for item in expected_behaviors
    )
    proven_journeys = sum(
        findings[item].state is EvidenceState.PROVEN
        for item in expected_journeys
    )
    not_evaluable_journeys = sum(
        findings[item].state in not_evaluable_states
        for item in expected_journeys
    )

    stable_receipts = tuple(sorted(set(receipt_ids)))
    semantic_payload = {
        "repository": assessment.repository,
        "sha": assessment.sha,
        "profile": assessment.profile.model_dump(mode="json"),
        "result": assessment.result.value,
        "required_behaviors": len(expected_behaviors),
        "proven_behaviors": proven_behaviors,
        "not_evaluable_behaviors": not_evaluable_behaviors,
        "critical_journeys_required": len(expected_journeys),
        "critical_journeys_proven": proven_journeys,
        "critical_journeys_not_evaluable": not_evaluable_journeys,
        "receipt_ids": list(stable_receipts),
    }
    return QualityExport(
        export_id=f"quality-export:{semantic_hash(semantic_payload)[:24]}",
        repository=assessment.repository,
        sha=assessment.sha,
        profile=assessment.profile,
        result=assessment.result,
        required_behaviors=len(expected_behaviors),
        proven_behaviors=proven_behaviors,
        not_evaluable_behaviors=not_evaluable_behaviors,
        critical_journeys_required=len(expected_journeys),
        critical_journeys_proven=proven_journeys,
        critical_journeys_not_evaluable=not_evaluable_journeys,
        receipt_ids=stable_receipts,
        generated_at=generated_at,
    )
