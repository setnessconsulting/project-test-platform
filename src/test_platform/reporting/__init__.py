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

MAX_JSON_INPUT_BYTES = 2_000_000
MAX_OUTPUT_BYTES = 2_000_000
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
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
    """Load one bounded UTF-8 JSON file."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ReportingError(f"cannot read JSON input: {path}") from exc
    if size > max_bytes:
        raise ReportingError(f"JSON input exceeds {max_bytes} bytes")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReportingError(f"invalid JSON input: {path}") from exc


def _looks_absolute_path(value: str) -> bool:
    return value.startswith("/") or bool(_WINDOWS_ABSOLUTE.match(value))


def public_safe_value(value: Any, *, key: str | None = None) -> Any:
    """Redact private-path and explicitly sensitive fields from structured output."""
    normalized_key = (key or "").lower().replace("-", "_")
    if any(marker in normalized_key for marker in _PRIVATE_FIELD_MARKERS):
        return "<redacted>"

    if isinstance(value, str):
        return "<redacted-path>" if _looks_absolute_path(value) else value
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
    public_safe: bool,
) -> dict[str, Any]:
    """Wrap a command result in the stable V1 output envelope."""
    safe_payload = public_safe_value(payload) if public_safe else payload
    return {
        "schema_version": "1",
        "tool_version": __version__,
        "command": command,
        "public_safe": public_safe,
        "payload": safe_payload,
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
