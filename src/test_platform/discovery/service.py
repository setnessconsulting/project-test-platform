"""Public discovery service assembled from the bounded core and registry."""

from __future__ import annotations

from pathlib import Path

from test_platform.contracts import DiscoveryReport
from test_platform.discovery.core import DiscoveryLimits, PluginRegistry, RepositoryIndex
from test_platform.discovery.plugins import builtin_plugins


def discover_repository(
    root: Path,
    *,
    limits: DiscoveryLimits | None = None,
) -> DiscoveryReport:
    """Discover configured test frameworks without executing repository code."""
    index = RepositoryIndex.build(root, limits=limits)
    registry = PluginRegistry(builtin_plugins())
    return registry.discover(index)
