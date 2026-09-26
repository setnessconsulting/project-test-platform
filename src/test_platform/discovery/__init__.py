"""Bounded repository test-framework discovery."""

from test_platform.discovery.core import (
    DiscoveryError,
    DiscoveryLimits,
    FrameworkPlugin,
    PluginRegistry,
    RepositoryIndex,
)
from test_platform.discovery.service import discover_repository

__all__ = [
    "DiscoveryError",
    "DiscoveryLimits",
    "FrameworkPlugin",
    "PluginRegistry",
    "RepositoryIndex",
    "discover_repository",
]
