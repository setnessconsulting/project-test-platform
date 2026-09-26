"""Versioned built-in Quality Profile library."""

from __future__ import annotations

from importlib.resources import files

from pydantic import ValidationError

from test_platform.contracts import QualityProfile
from test_platform.yaml_io import YamlContractError, parse_yaml_mapping

PROFILE_FILES: dict[str, str] = {
    "python-control-plane-v1": "python-control-plane-v1.yaml",
    "typescript-control-plane-v1": "typescript-control-plane-v1.yaml",
    "web-application-v1": "web-application-v1.yaml",
    "browser-game-v1": "browser-game-v1.yaml",
    "static-site-v1": "static-site-v1.yaml",
    "local-agent-v1": "local-agent-v1.yaml",
    "infrastructure-tool-v1": "infrastructure-tool-v1.yaml",
    "documentation-tool-v1": "documentation-tool-v1.yaml",
}


class ProfileError(ValueError):
    """Raised when a profile ID or built-in profile is invalid."""


def load_profile(profile_id: str) -> QualityProfile:
    """Load one allowlisted built-in V1 profile."""
    filename = PROFILE_FILES.get(profile_id)
    if filename is None:
        raise ProfileError(f"unsupported Quality Profile: {profile_id}")

    resource = files("test_platform").joinpath("data", "profiles", "v1", filename)
    try:
        text = resource.read_text(encoding="utf-8")
        data = parse_yaml_mapping(text, source=f"profile:{profile_id}")
        profile = QualityProfile.model_validate(data)
    except (OSError, ValidationError, YamlContractError) as exc:
        raise ProfileError(f"invalid built-in Quality Profile: {profile_id}") from exc

    if profile.profile_id != profile_id:
        raise ProfileError(
            f"profile file identity mismatch: expected {profile_id}, got {profile.profile_id}"
        )
    return profile


def load_all_profiles() -> tuple[QualityProfile, ...]:
    """Load all built-in V1 profiles in deterministic ID order."""
    return tuple(load_profile(profile_id) for profile_id in sorted(PROFILE_FILES))
