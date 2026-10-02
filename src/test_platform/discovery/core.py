"""Bounded deterministic repository discovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from test_platform.contracts import DiscoveryReport, DiscoveryState, FrameworkDiscovery
from test_platform.filesystem_safety import bounded_walk, is_indirect

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
    """Hard traversal and file-read bounds.

    Every bound is fail-closed: exceeding one yields ``LIMIT_EXCEEDED`` rather
    than a silently incomplete report. Directory count and total entry count
    are bounded in addition to file count and depth, because a tree of empty
    directories contains no files and would otherwise never trip a file cap.
    """

    max_files: int = 20_000
    max_depth: int = 12
    max_text_bytes: int = 1_000_000
    max_directories: int = 20_000
    max_entries: int = 60_000
    max_total_bytes: int = 200_000_000


@dataclass(frozen=True)
class FileRecord:
    """One indexed repository file."""

    relative_path: str
    size: int


class DiscoveryError(ValueError):
    """Raised when a requested root cannot be safely inspected."""


def _walk_repository(
    root: Path,
    limits: DiscoveryLimits,
) -> tuple[tuple[tuple[Path, tuple[Path, ...]], ...], bool]:
    """Return bounded, non-following ``(directory, files)`` pairs under root.

    Depth and breadth limits are reported through the second return value so
    the caller can mark the index truncated and report ``LIMIT_EXCEEDED``.
    """
    directories, limit_exceeded = bounded_walk(
        root,
        max_depth=limits.max_depth,
        max_directories=limits.max_directories,
        max_entries=limits.max_entries,
    )
    filtered = tuple(
        (
            directory,
            tuple(
                path
                for path in files
                if not any(part in IGNORED_PARTS for part in path.parts)
            ),
        )
        for directory, files in directories
    )
    return filtered, limit_exceeded


class FrameworkPlugin(Protocol):
    """Versioned framework discovery plugin contract."""

    @property
    def framework_id(self) -> str:
        """Stable framework identifier."""

    @property
    def adapter_version(self) -> str:
        """Version of the discovery adapter contract."""

    def discover(self, index: RepositoryIndex) -> FrameworkDiscovery:
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
    ) -> RepositoryIndex:
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
        total_bytes = 0
        directories, limit_exceeded = _walk_repository(root, limits)
        truncated = limit_exceeded

        for _current_path, files in directories:
            if truncated:
                break
            for path in files:
                if len(records) >= limits.max_files:
                    truncated = True
                    break
                try:
                    size = path.stat().st_size
                    relative = path.relative_to(root).as_posix()
                except OSError:
                    # An unreadable entry makes the index indeterminate; never
                    # report a partial tree as a complete one.
                    truncated = True
                    continue
                total_bytes += size
                if total_bytes > limits.max_total_bytes:
                    truncated = True
                    break
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
        if not resolved.is_relative_to(self.root) or is_indirect(candidate):
            return None
        try:
            # Bound at open time rather than trusting the size observed during
            # indexing: a file replaced or grown since then must not be read
            # into memory in full.
            with resolved.open("rb") as handle:
                raw = handle.read(self.limits.max_text_bytes + 1)
            if len(raw) > self.limits.max_text_bytes:
                return None
            return raw.decode("utf-8")
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

        diagnostics: tuple[str, ...]

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
