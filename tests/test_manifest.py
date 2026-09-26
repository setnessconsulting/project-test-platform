from __future__ import annotations

from pathlib import Path

import pytest

from test_platform.manifest import ManifestError, load_manifest


@pytest.mark.parametrize(
    "example",
    [
        "python-control-plane",
        "web-application",
        "browser-game",
        "infrastructure-tool",
    ],
)
def test_example_manifests_validate(example: str) -> None:
    manifest = load_manifest(Path("examples") / example / ".test-platform.yaml")

    assert manifest.profile.profile_id


def test_manifest_rejects_path_escape(tmp_path: Path) -> None:
    path = tmp_path / ".test-platform.yaml"
    path.write_text(
        """
schema_version: "1"
profile:
  profile_id: web-application-v1
  version: 1.0.0
behaviors_path: ../secret.yaml
suites: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="bounded relative"):
        load_manifest(path)


def test_manifest_rejects_shell_command_entrypoint(tmp_path: Path) -> None:
    path = tmp_path / ".test-platform.yaml"
    path.write_text(
        """
schema_version: "1"
profile:
  profile_id: web-application-v1
  version: 1.0.0
behaviors_path: quality/behaviors.yaml
suites:
  - suite_id: e2e
    entrypoint: npm test && curl example.invalid
    trust: pr-untrusted
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="invalid repository manifest"):
        load_manifest(path)


def test_manifest_rejects_unknown_profile(tmp_path: Path) -> None:
    path = tmp_path / ".test-platform.yaml"
    path.write_text(
        """
schema_version: "1"
profile:
  profile_id: made-up-profile-v1
  version: 1.0.0
behaviors_path: quality/behaviors.yaml
suites: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="unsupported Quality Profile"):
        load_manifest(path)


def test_manifest_rejects_secret_shaped_value(tmp_path: Path) -> None:
    token = "gh" + "p_" + ("a" * 24)
    path = tmp_path / ".test-platform.yaml"
    path.write_text(
        f"""
schema_version: "1"
profile:
  profile_id: web-application-v1
  version: 1.0.0
behaviors_path: quality/behaviors.yaml
suites: []
credential: {token}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="forbidden github-token"):
        load_manifest(path)
