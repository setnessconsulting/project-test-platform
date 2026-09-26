"""Bounded deterministic repository discovery."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from test_platform.contracts import DiscoveryReport, DiscoveryState, FrameworkDiscovery

IGNORED_PARTS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        "coverage",
        "artifacts",
        ".private",
    }
)


@dataclass(frozen=True)
class DiscoveryLimits:
    """Hard traversal and file-read bounds."""

    max_files: int = 20_000
    max_depth: int = 12
    max_text_bytes: int = 1_000_000


@dataclass(frozen=True)
class FileRecord:
    """One indexed repository file."""

    relative_path: str
    size: int


class DiscoveryError(ValueError):
    """Raised when a requested root cannot be safely inspected."""


class FrameworkPlugin(Protocol):
    """Versioned framework discovery plugin contract."""

    framework_id: str
    adapter_version: str

    def discover(self, index: "RepositoryIndex") -> FrameworkDiscovery:
        """Return deterministic discovery state for this framework."""


class RepositoryIndex:
    """Bounded immutable view over an explicitly selected repository root."""

    def __init__(
        self,
        root: Path,
        files: tuple[FileRecord, ...],
        limits: DiscoveryLimits,
        *,
        truncated: bool,
    ) -> None:
        self.root = root
        self.files = files
        self.limits = limits
        self.truncated = truncated
        self._by_path = {item.relative_path: item for item in files}

    @classmethod
    def build(
        cls,
        root: Path,
        limits: DiscoveryLimits | None = None,
    ) -> "RepositoryIndex":
        """Index one explicit repository-like root without following symlinks."""
        limits = limits or DiscoveryLimits()
        root = root.resolve()

        if not root.is_dir():
            raise DiscoveryError("discovery root must be an existing directory")
        if root == Path(root.anchor):
            raise DiscoveryError("filesystem root cannot be used as a discovery root")
        if not ((root / ".test-platform.yaml").exists() or (root / ".git").exists()):
            raise DiscoveryError(
                "discovery root must contain .test-platform.yaml or .git"
            )

        records: list[FileRecord] = []
        truncated = False

        for current, dirs, filenames in os.walk(root, followlinks=False):
            current_path = Path(current)
            try:
                relative_dir = current_path.relative_to(root)
            except ValueError as exc:
                raise DiscoveryError("discovery escaped requested root") from exc

            depth = len(relative_dir.parts)
            if depth >= limits.max_depth:
                dirs[:] = []
            else:
                safe_dirs: list[str] = []
                for name in sorted(dirs):
                    candidate = current_path / name
                    if name in IGNORED_PARTS or candidate.is_symlink():
                        continue
                    safe_dirs.append(name)
                dirs[:] = safe_dirs

            for filename in sorted(filenames):
                if len(records) >= limits.max_files:
                    truncated = True
                    dirs[:] = []
                    break
                path = current_path / filename
                if path.is_symlink() or not path.is_file():
                    continue
                try:
                    size = path.stat().st_size
                    relative = path.relative_to(root).as_posix()
                except OSError:
                    continue
                records.append(FileRecord(relative_path=relative, size=size))

            if truncated:
                break

        return cls(
            root=root,
            files=tuple(records),
            limits=limits,
            truncated=truncated,
        )

    def paths(self) -> tuple[str, ...]:
        """Return indexed paths in deterministic order."""
        return tuple(item.relative_path for item in self.files)

    def matching_suffix(self, suffix: str) -> tuple[str, ...]:
        """Return paths ending in suffix."""
        return tuple(
            item.relative_path
            for item in self.files
            if item.relative_path.endswith(suffix)
        )

    def basename_matches(self, names: frozenset[str]) -> tuple[str, ...]:
        """Return paths whose basename is in an allowlist."""
        return tuple(
            item.relative_path
            for item in self.files
            if PurePathName(item.relative_path).name in names
        )

    def read_text(self, relative_path: str) -> str | None:
        """Read one indexed bounded UTF-8 file; never follow arbitrary paths."""
        record = self._by_path.get(relative_path)
        if record is None or record.size > self.limits.max_text_bytes:
            return None

        candidate = self.root / Path(*relative_path.split("/"))
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            return None
        if not resolved.is_relative_to(self.root) or candidate.is_symlink():
            return None
        try:
            return resolved.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return None


@dataclass(frozen=True)
class PurePathName:
    """Tiny path-name helper without host-path interpretation."""

    value: str

    @property
    def name(self) -> str:
        return self.value.rsplit("/", 1)[-1]


class PluginRegistry:
    """Fail-closed deterministic plugin registry."""

    def __init__(self, plugins: tuple[FrameworkPlugin, ...] = ()) -> None:
        by_id: dict[str, FrameworkPlugin] = {}
        for plugin in plugins:
            if plugin.framework_id in by_id:
                raise DiscoveryError(
                    f"duplicate discovery plugin: {plugin.framework_id}"
                )
            by_id[plugin.framework_id] = plugin
        self._plugins = tuple(by_id[key] for key in sorted(by_id))

    @property
    def plugins(self) -> tuple[FrameworkPlugin, ...]:
        return self._plugins

    def discover(self, index: RepositoryIndex) -> DiscoveryReport:
        """Run only registered static discovery plugins."""
        observations = tuple(plugin.discover(index) for plugin in self._plugins)
        detected = tuple(
            item for item in observations if item.state is not DiscoveryState.UNKNOWN
        )

        if index.truncated:
            state = DiscoveryState.LIMIT_EXCEEDED
            diagnostics = ("repository file limit exceeded; discovery is incomplete",)
        elif any(item.state is DiscoveryState.MALFORMED for item in detected):
            state = DiscoveryState.MALFORMED
            diagnostics = ("one or more framework configs are malformed",)
        elif any(item.state is DiscoveryState.DETECTED for item in detected):
            state = DiscoveryState.DETECTED
            diagnostics = ()
        else:
            state = DiscoveryState.UNKNOWN
            diagnostics = ("no supported test framework detected",)

        return DiscoveryReport(
            state=state,
            frameworks=detected,
            files_scanned=len(index.files),
            truncated=index.truncated,
            diagnostics=diagnostics,
        )
