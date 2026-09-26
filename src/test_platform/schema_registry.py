"""Generate and check the versioned public JSON Schema bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaMode, models_json_schema

from test_platform.canonical import canonical_json
from test_platform.contracts import PUBLIC_SCHEMA_MODELS

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_ID = "https://setnessconsulting.github.io/project-test-platform/schemas/v1/contracts.schema.json"


def expected_schema_bundle() -> dict[str, Any]:
    """Build the deterministic language-neutral V1 schema bundle."""
    model_inputs: list[tuple[type[BaseModel], JsonSchemaMode]] = [
        (model, "validation") for model in PUBLIC_SCHEMA_MODELS
    ]
    _, schema = models_json_schema(model_inputs, title="Project Test Platform V1 contracts")
    schema["$schema"] = SCHEMA_DIALECT
    schema["$id"] = SCHEMA_ID
    schema["x-contract-fragments"] = {
        model.__name__: f"#/$defs/{model.__name__}" for model in PUBLIC_SCHEMA_MODELS
    }
    return schema


def write_schema_bundle(path: Path) -> None:
    """Write the canonical bundle with deterministic formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(expected_schema_bundle(), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def check_schema_bundle(path: Path) -> bool:
    """Return whether the checked-in bundle matches generated contracts semantically."""
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return canonical_json(actual) == canonical_json(expected_schema_bundle())


def main(argv: list[str] | None = None) -> int:
    """Generate or check the checked-in V1 schema bundle."""
    parser = argparse.ArgumentParser(description="Generate/check Test Platform JSON Schemas.")
    parser.add_argument(
        "path",
        nargs="?",
        default="schemas/v1/contracts.schema.json",
        type=Path,
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    if args.check:
        if check_schema_bundle(args.path):
            print("schema-bundle: PASS")
            return 0
        print("schema-bundle: FAIL")
        return 1

    write_schema_bundle(args.path)
    print(args.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
