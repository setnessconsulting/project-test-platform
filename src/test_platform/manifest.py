"""Repository manifest loading and fail-closed validation."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from test_platform.contracts import RepositoryManifest
from test_platform.profiles import ProfileError, load_profile
from test_platform.yaml_io import YamlContractError, parse_yaml_mapping

MAX_MANIFEST_BYTES = 256 * 1024


class ManifestError(ValueError):
    """Raised when a repository manifest is unsafe or incompatible."""


def _validate_relative_path(value: str, *, field: str) -> None:
    if "\\" in value:
        raise ManifestError(f"{field} must use portable forward-slash paths")
    path = PurePosixPath(value)
    if path.is_absolute() or not value or any(part in {"", ".", ".."} for part in path.parts):
        raise ManifestError(f"{field} must be a bounded relative repository path")


def load_manifest(path: Path) -> RepositoryManifest:
    """Load and validate the root .test-platform.yaml contract."""
    if path.name != ".test-platform.yaml":
        raise ManifestError("manifest filename must be .test-platform.yaml")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ManifestError(f"cannot read manifest: {path}") from exc
    if size > MAX_MANIFEST_BYTES:
        raise ManifestError("manifest exceeds maximum size")

    try:
        data = parse_yaml_mapping(path.read_text(encoding="utf-8"), source=str(path))
        manifest = RepositoryManifest.model_validate(data)
    except (OSError, ValidationError, YamlContractError) as exc:
        raise ManifestError(f"invalid repository manifest: {path}") from exc

    _validate_relative_path(manifest.behaviors_path, field="behaviors_path")

    try:
        profile = load_profile(manifest.profile.profile_id)
    except ProfileError as exc:
        raise ManifestError(str(exc)) from exc
    if profile.version != manifest.profile.version:
        raise ManifestError(
            f"unsupported profile version for {profile.profile_id}: "
            f"{manifest.profile.version}; expected {profile.version}"
        )
    return manifest
