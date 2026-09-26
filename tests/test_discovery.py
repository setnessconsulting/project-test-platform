from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_platform.contracts import DiscoveryState
from test_platform.discovery import (
    DiscoveryError,
    DiscoveryLimits,
    PluginRegistry,
    RepositoryIndex,
    discover_repository,
)
from test_platform.discovery.plugins import PytestDiscoveryPlugin


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".test-platform.yaml").write_text("schema_version: '1'\n", encoding="utf-8")
    return root


def test_mixed_framework_repository_is_discovered_deterministically(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\naddopts = '-q'\n",
        encoding="utf-8",
    )
    (root / "test_example.py").write_text("def test_x(): pass\n", encoding="utf-8")
    (root / "package.json").write_text(
        json.dumps(
            {
                "devDependencies": {
                    "vitest": "1.0.0",
                    "@playwright/test": "1.0.0",
                },
                "scripts": {
                    "test": "arbitrary repository-controlled command body",
                    "test:e2e": "another repository-controlled command body",
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "playwright.config.ts").write_text("export default {}\n", encoding="utf-8")
    (root / "sample.Tests.ps1").write_text("Describe 'sample' {}\n", encoding="utf-8")

    first = discover_repository(root)
    second = discover_repository(root)

    assert first == second
    assert first.state is DiscoveryState.DETECTED
    assert [item.framework for item in first.frameworks] == [
        "pester",
        "playwright",
        "pytest",
        "vitest",
    ]
    vitest = next(item for item in first.frameworks if item.framework == "vitest")
    assert vitest.command_ids == ("test", "test:e2e")
    assert "arbitrary repository-controlled command body" not in repr(first)


def test_unsupported_framework_yields_unknown(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "Cargo.toml").write_text("[package]\nname='sample'\n", encoding="utf-8")

    report = discover_repository(root)

    assert report.state is DiscoveryState.UNKNOWN
    assert report.frameworks == ()


def test_malformed_framework_config_is_explicit(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "package.json").write_text(
        '{"devDependencies":{"vitest":"1.0.0"',
        encoding="utf-8",
    )

    report = discover_repository(root)

    assert report.state is DiscoveryState.MALFORMED
    assert report.frameworks[0].framework == "vitest"
    assert report.frameworks[0].state is DiscoveryState.MALFORMED


def test_file_limit_returns_incomplete_state(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    for number in range(10):
        (root / f"test_{number}.py").write_text("pass\n", encoding="utf-8")

    report = discover_repository(root, limits=DiscoveryLimits(max_files=3))

    assert report.state is DiscoveryState.LIMIT_EXCEEDED
    assert report.truncated is True
    assert report.files_scanned == 3


def test_dependency_directories_and_symlinks_are_not_scanned(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    node_modules = root / "node_modules"
    node_modules.mkdir()
    (node_modules / "fake.test.ts").write_text("ignored\n", encoding="utf-8")

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "test_escape.py").write_text("ignored\n", encoding="utf-8")
    link = root / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")

    report = discover_repository(root)

    assert report.state is DiscoveryState.UNKNOWN
    assert all("node_modules" not in path for item in report.frameworks for path in item.test_paths)
    assert all("linked" not in path for item in report.frameworks for path in item.test_paths)


def test_discovery_requires_repository_like_explicit_root(tmp_path: Path) -> None:
    with pytest.raises(DiscoveryError, match="must contain"):
        RepositoryIndex.build(tmp_path)


def test_plugin_registry_rejects_duplicate_framework_ids() -> None:
    plugin = PytestDiscoveryPlugin()

    with pytest.raises(DiscoveryError, match="duplicate discovery plugin"):
        PluginRegistry((plugin, plugin))
