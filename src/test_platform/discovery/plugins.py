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
            if (
                name.startswith("test_") and name.endswith(".py")
            ) or name.endswith("_test.py"):
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
        elif configs:
            state = DiscoveryState.DETECTED
        else:
            state = DiscoveryState.UNKNOWN
            tests = []

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
        candidate_tests: list[str] = []
        commands: list[str] = []
        malformed: list[str] = []

        for path in index.paths():
            name = path.rsplit("/", 1)[-1]
            if name in self.config_names:
                configs.append(path)
            if _looks_like_node_test(path, self.framework_id):
                candidate_tests.append(path)
            if name != "package.json":
                continue

            text = index.read_text(path)
            if text is None:
                continue
            try:
                package = json.loads(text)
            except json.JSONDecodeError:
                # The file cannot be parsed, so dependency evidence is unavailable.
                # Attribute it only when the raw text names this framework as an
                # exact quoted dependency key, and report nothing at all for every
                # other Node framework: an unparseable package.json does not prove
                # that jest, vitest, and playwright are all present.
                if _declares_exact_dependency_key(text, self.package_names):
                    malformed.append(path)
                continue
            if not isinstance(package, dict):
                if _declares_exact_dependency_key(text, self.package_names):
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
            tests = []
        elif configs:
            # A framework is only present when a real config file or an actual
            # dependency proves it. Bare test paths are collected as candidates
            # because naming alone is not evidence of a runner: a repository can
            # hold jest, vitest, and playwright specs side by side, and attributing
            # all of them to every Node framework invents inventory and lets one
            # framework's evidence appear to cover another's journeys.
            state = DiscoveryState.DETECTED
            tests = candidate_tests
        else:
            state = DiscoveryState.UNKNOWN
            tests = []

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


def _declares_exact_dependency_key(text: str, package_names: frozenset[str]) -> bool:
    """Return whether raw JSON text names a package as an exact quoted key.

    Used only when ``package.json`` cannot be parsed. A substring test such as
    ``"jest" in text`` also matches unrelated packages that embed the name, for
    example ``@testing-library/jest-dom``, and would invent a framework the
    repository never uses. Requiring the full quoted key keeps attribution
    honest even when the file is unparseable.
    """
    return any(f'"{package}"' in text for package in package_names)


def _looks_like_node_test(path: str, framework: str) -> bool:
    """Match a path only against the owning framework's own test conventions.

    Node test naming is not disjoint across frameworks: a Playwright
    ``.spec.ts`` must never be claimed by jest or vitest, and a unit
    ``.test.ts`` must never be claimed by Playwright. Claiming a foreign
    framework's path inflates inventory counts and lets the wrong executor's
    evidence appear to cover a behavior it never ran.
    """
    lowered = path.lower()
    spec_suffixes = (".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx")
    unit_suffixes = (".test.ts", ".test.tsx", ".test.js", ".test.jsx")

    if framework == "playwright":
        # Playwright drives assembled browser journeys; its specs use .spec.*,
        # and its suites conventionally live under an e2e-style directory.
        return lowered.endswith(spec_suffixes) or "/e2e/" in f"/{lowered}"
    return lowered.endswith(unit_suffixes)


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
