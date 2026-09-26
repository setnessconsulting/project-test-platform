from __future__ import annotations

from pathlib import Path

import pytest

from test_platform.manifest import ManifestError, load_manifest


def _write_manifest(path: Path, behaviors_path: str) -> None:
    path.write_text(
        f"""
schema_version: "1"
profile:
  profile_id: web-application-v1
  version: 1.0.0
behaviors_path: {behaviors_path}
suites: []
""",
        encoding="utf-8",
    )


def test_manifest_rejects_behavior_path_symlink_escape(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    (outside / "behaviors.yaml").write_text("schema_version: '1'\nbehaviors: []\n", encoding="utf-8")

    link = repo / "quality"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable in this environment")

    manifest_path = repo / ".test-platform.yaml"
    _write_manifest(manifest_path, "quality/behaviors.yaml")

    with pytest.raises(ManifestError, match="outside|symlink"):
        load_manifest(manifest_path)


def test_manifest_rejects_manifest_symlink(tmp_path: Path) -> None:
    actual = tmp_path / "actual.yaml"
    _write_manifest(actual, "quality/behaviors.yaml")
    link = tmp_path / ".test-platform.yaml"
    try:
        link.symlink_to(actual)
    except OSError:
        pytest.skip("symlink creation unavailable in this environment")

    with pytest.raises(ManifestError, match="must not be a symlink"):
        load_manifest(link)
