"""Repository manifest loading and fail-closed validation."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from test_platform.contracts import RepositoryManifest
from test_platform.filesystem_safety import is_indirect
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


def _validate_repo_child(root: Path, relative: str, *, field: str) -> None:
    """Reject symlink/path escapes for a declared repository-local path."""
    root_resolved = root.resolve()
    candidate = root / Path(*PurePosixPath(relative).parts)
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise ManifestError(f"{field} cannot be resolved safely") from exc
    if not resolved.is_relative_to(root_resolved):
        raise ManifestError(f"{field} resolves outside the repository root")

    current = root_resolved
    for part in PurePosixPath(relative).parts:
        current = current / part
        if is_indirect(current):
            raise ManifestError(f"{field} must not traverse a link or junction")


def load_manifest(path: Path) -> RepositoryManifest:
    """Load and validate the root .test-platform.yaml contract."""
    if path.name != ".test-platform.yaml":
        raise ManifestError("manifest filename must be .test-platform.yaml")
    if is_indirect(path):
        raise ManifestError("manifest must not be a link or junction")
    try:
        size = path.stat().st_size
    except OSError as exc:
        # Name only: a host path here would be printed to stderr.
        raise ManifestError(f"cannot read manifest: {path.name}") from exc
    if size > MAX_MANIFEST_BYTES:
        raise ManifestError("manifest exceeds maximum size")

    try:
        data = parse_yaml_mapping(path.read_text(encoding="utf-8"), source=str(path))
        manifest = RepositoryManifest.model_validate(data)
    except YamlContractError as exc:
        raise ManifestError(str(exc)) from exc
    except (OSError, ValidationError) as exc:
        raise ManifestError(f"invalid repository manifest: {path.name}") from exc

    _validate_relative_path(manifest.behaviors_path, field="behaviors_path")
    _validate_repo_child(path.parent, manifest.behaviors_path, field="behaviors_path")

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
