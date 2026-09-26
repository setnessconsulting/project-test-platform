"""Static built-in test-framework discovery plugins."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass

from test_platform.contracts import DiscoveryState, FrameworkDiscovery
from test_platform.discovery.core import FrameworkPlugin, RepositoryIndex


def _sorted_unique(values: list[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


@dataclass(frozen=True)
class PytestDiscoveryPlugin:
    framework_id: str = "pytest"
    adapter_version: str = "1"

    def discover(self, index: RepositoryIndex) -> FrameworkDiscovery:
        configs: list[str] = []
        tests: list[str] = []
        malformed: list[str] = []

        for path in index.paths():
            name = path.rsplit("/", 1)[-1]
            if name in {"pytest.ini", "conftest.py"}:
                configs.append(path)
            if name.startswith("test_") and name.endswith(".py"):
                tests.append(path)
            elif name.endswith("_test.py"):
                tests.append(path)

            if name == "pyproject.toml":
                text = index.read_text(path)
                if text is None:
                    continue
                if "[tool.pytest" not in text:
                    continue
                try:
                    tomllib.loads(text)
                except tomllib.TOMLDecodeError:
                    malformed.append(path)
                else:
                    configs.append(path)

        if malformed:
            state = DiscoveryState.MALFORMED
        elif configs or tests:
            state = DiscoveryState.DETECTED
        else:
            state = DiscoveryState.UNKNOWN

        return FrameworkDiscovery(
            framework=self.framework_id,
            adapter_version=self.adapter_version,
            state=state,
            config_paths=_sorted_unique(configs),
            test_paths=_sorted_unique(tests),
            result_formats=("junit-xml",) if state is not DiscoveryState.UNKNOWN else (),
            diagnostics=tuple(
                f"malformed pytest TOML config: {path}" for path in sorted(malformed)
            ),
        )


@dataclass(frozen=True)
class NodeFrameworkDiscoveryPlugin:
    framework_id: str
    package_names: frozenset[str]
    config_names: frozenset[str]
    adapter_version: str = "1"

    def discover(self, index: RepositoryIndex) -> FrameworkDiscovery:
        configs: list[str] = []
        tests: list[str] = []
        commands: list[str] = []
        malformed: list[str] = []

        for path in index.paths():
            name = path.rsplit("/", 1)[-1]
            if name in self.config_names:
                configs.append(path)
            if _looks_like_node_test(path, self.framework_id):
                tests.append(path)
            if name != "package.json":
                continue

            text = index.read_text(path)
            if text is None:
                continue
            raw_mentions_framework = any(package in text for package in self.package_names)
            if not raw_mentions_framework:
                continue
            try:
                package = json.loads(text)
            except json.JSONDecodeError:
                malformed.append(path)
                continue
            if not isinstance(package, dict):
                malformed.append(path)
                continue

            dependencies = {}
            for field in ("dependencies", "devDependencies", "peerDependencies"):
                value = package.get(field)
                if isinstance(value, dict):
                    dependencies.update(value)

            if not any(name in dependencies for name in self.package_names):
                continue

            configs.append(path)
            scripts = package.get("scripts")
            if isinstance(scripts, dict):
                for script_name in scripts:
                    if isinstance(script_name, str) and _safe_identifier(script_name):
                        commands.append(script_name)

        if malformed:
            state = DiscoveryState.MALFORMED
        elif configs or tests:
            state = DiscoveryState.DETECTED
        else:
            state = DiscoveryState.UNKNOWN

        return FrameworkDiscovery(
            framework=self.framework_id,
            adapter_version=self.adapter_version,
            state=state,
            config_paths=_sorted_unique(configs),
            test_paths=_sorted_unique(tests),
            command_ids=_sorted_unique(commands),
            result_formats=("junit-xml",) if state is not DiscoveryState.UNKNOWN else (),
            diagnostics=tuple(
                f"malformed package.json for {self.framework_id}: {path}"
                for path in sorted(malformed)
            ),
        )


@dataclass(frozen=True)
class PesterDiscoveryPlugin:
    framework_id: str = "pester"
    adapter_version: str = "1"

    def discover(self, index: RepositoryIndex) -> FrameworkDiscovery:
        tests = [
            path for path in index.paths() if path.lower().endswith(".tests.ps1")
        ]
        configs = [
            path
            for path in index.paths()
            if path.rsplit("/", 1)[-1].lower() == "pesterconfiguration.psd1"
        ]
        state = (
            DiscoveryState.DETECTED
            if tests or configs
            else DiscoveryState.UNKNOWN
        )
        return FrameworkDiscovery(
            framework=self.framework_id,
            adapter_version=self.adapter_version,
            state=state,
            config_paths=_sorted_unique(configs),
            test_paths=_sorted_unique(tests),
            result_formats=("nunit-xml", "junit-xml")
            if state is DiscoveryState.DETECTED
            else (),
        )


def _safe_identifier(value: str) -> bool:
    if not value or len(value) > 128:
        return False
    return all(character.isalnum() or character in "._:-" for character in value)


def _looks_like_node_test(path: str, framework: str) -> bool:
    lowered = path.lower()
    if framework == "playwright":
        return (
            lowered.endswith(".spec.ts")
            or lowered.endswith(".spec.js")
            or "/e2e/" in f"/{lowered}"
        )
    return any(
        lowered.endswith(suffix)
        for suffix in (
            ".test.ts",
            ".test.tsx",
            ".test.js",
            ".test.jsx",
            ".spec.ts",
            ".spec.tsx",
            ".spec.js",
            ".spec.jsx",
        )
    )


def builtin_plugins() -> tuple[FrameworkPlugin, ...]:
    """Return the deterministic built-in discovery plugin set."""
    return (
        NodeFrameworkDiscoveryPlugin(
            framework_id="jest",
            package_names=frozenset({"jest", "@jest/core"}),
            config_names=frozenset(
                {
                    "jest.config.js",
                    "jest.config.cjs",
                    "jest.config.mjs",
                    "jest.config.ts",
                }
            ),
        ),
        PesterDiscoveryPlugin(),
        NodeFrameworkDiscoveryPlugin(
            framework_id="playwright",
            package_names=frozenset({"@playwright/test"}),
            config_names=frozenset(
                {
                    "playwright.config.js",
                    "playwright.config.mjs",
                    "playwright.config.ts",
                }
            ),
        ),
        PytestDiscoveryPlugin(),
        NodeFrameworkDiscoveryPlugin(
            framework_id="vitest",
            package_names=frozenset({"vitest"}),
            config_names=frozenset(
                {
                    "vitest.config.js",
                    "vitest.config.mjs",
                    "vitest.config.ts",
                }
            ),
        ),
    )
