from __future__ import annotations

import pytest

from test_platform.contracts import (
    DiscoveryReport,
    DiscoveryState,
    EvidenceClass,
    FrameworkDiscovery,
)
from test_platform.inventory import InventoryError, build_inventory


def test_inventory_is_deterministic_and_keeps_behavior_links_explicit() -> None:
    discovery = DiscoveryReport(
        state=DiscoveryState.DETECTED,
        files_scanned=3,
        frameworks=(
            FrameworkDiscovery(
                framework="playwright",
                adapter_version="1",
                state=DiscoveryState.DETECTED,
                test_paths=("e2e/login.spec.ts",),
            ),
            FrameworkDiscovery(
                framework="pytest",
                adapter_version="1",
                state=DiscoveryState.DETECTED,
                test_paths=("tests/test_policy.py",),
            ),
        ),
    )
    links = {
        "playwright:e2e/login.spec.ts": ("auth.sign-in",),
        "pytest:tests/test_policy.py": ("policy.target-binding",),
    }

    first = build_inventory(
        repository="setnessconsulting/example",
        sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        discovery=discovery,
        behavior_links=links,
    )
    second = build_inventory(
        repository="setnessconsulting/example",
        sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        discovery=discovery,
        behavior_links=links,
    )

    assert first == second
    assert [item.test_id for item in first.inventory.tests] == [
        "playwright:e2e/login.spec.ts",
        "pytest:tests/test_policy.py",
    ]
    assert first.inventory.tests[0].evidence_class is EvidenceClass.E2E
    assert first.inventory.tests[1].evidence_class is EvidenceClass.DETERMINISTIC
    assert first.inventory.tests[0].behavior_ids == ("auth.sign-in",)


def test_same_path_from_multiple_frameworks_is_diagnostic_not_silently_collapsed() -> None:
    discovery = DiscoveryReport(
        state=DiscoveryState.DETECTED,
        files_scanned=1,
        frameworks=(
            FrameworkDiscovery(
                framework="jest",
                adapter_version="1",
                state=DiscoveryState.DETECTED,
                test_paths=("src/example.test.ts",),
            ),
            FrameworkDiscovery(
                framework="vitest",
                adapter_version="1",
                state=DiscoveryState.DETECTED,
                test_paths=("src/example.test.ts",),
            ),
        ),
    )

    result = build_inventory(
        repository="setnessconsulting/example",
        sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        discovery=discovery,
    )

    assert len(result.inventory.tests) == 2
    assert result.diagnostics[0].code == "ambiguous-framework-path"


def test_unknown_behavior_link_target_is_visible() -> None:
    discovery = DiscoveryReport(
        state=DiscoveryState.UNKNOWN,
        files_scanned=0,
        frameworks=(),
    )

    result = build_inventory(
        repository="setnessconsulting/example",
        sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        discovery=discovery,
        behavior_links={"pytest:missing.py": ("missing.behavior",)},
    )

    assert result.inventory.tests == ()
    assert result.diagnostics[0].code == "unknown-behavior-link-target"


@pytest.mark.parametrize("state", [DiscoveryState.MALFORMED, DiscoveryState.LIMIT_EXCEEDED])
def test_incomplete_discovery_cannot_be_represented_as_complete_inventory(
    state: DiscoveryState,
) -> None:
    discovery = DiscoveryReport(
        state=state,
        files_scanned=1,
        frameworks=(),
        truncated=state is DiscoveryState.LIMIT_EXCEEDED,
    )

    with pytest.raises(InventoryError):
        build_inventory(
            repository="setnessconsulting/example",
            sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            discovery=discovery,
        )
