"""Normalized test inventory package."""

from test_platform.inventory.core import (
    InventoryBuildResult,
    InventoryDiagnostic,
    InventoryError,
    build_inventory,
    stable_test_id,
)

__all__ = [
    "InventoryBuildResult",
    "InventoryDiagnostic",
    "InventoryError",
    "build_inventory",
    "stable_test_id",
]
