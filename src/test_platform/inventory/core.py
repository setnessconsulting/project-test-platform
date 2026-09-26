"""Normalized repository test inventory built from bounded discovery evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from test_platform.contracts import (
    DiscoveryReport,
    DiscoveryState,
    EvidenceClass,
    TestCaseObservation,
    TestInventory,
)


class InventoryError(ValueError):
    """Raised when discovery evidence is not safe to represent as a complete inventory."""


DEFAULT_FRAMEWORK_EVIDENCE: Mapping[str, EvidenceClass] = {
    "pytest": EvidenceClass.DETERMINISTIC,
    "jest": EvidenceClass.DETERMINISTIC,
    "vitest": EvidenceClass.DETERMINISTIC,
    "playwright": EvidenceClass.E2E,
    "pester": EvidenceClass.DETERMINISTIC,
}


@dataclass(frozen=True)
class InventoryDiagnostic:
    """One deterministic, non-fatal inventory diagnostic."""

    code: str
    message: str
    test_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class InventoryBuildResult:
    """Inventory plus diagnostics that must remain visible to callers."""

    inventory: TestInventory
    diagnostics: tuple[InventoryDiagnostic, ...] = ()


def stable_test_id(framework: str, path: str) -> str:
    """Return a stable path-level test identity without inspecting source code."""
    normalized = path.replace("\\", "/").lstrip("./")
    return f"{framework}:{normalized}"


def build_inventory(
    *,
    repository: str,
    sha: str,
    discovery: DiscoveryReport,
    behavior_links: Mapping[str, tuple[str, ...]] | None = None,
    framework_evidence: Mapping[str, EvidenceClass] | None = None,
) -> InventoryBuildResult:
    """Build a deterministic inventory without executing or parsing test source.

    Discovery states that prove the scan is incomplete fail closed. UNKNOWN is allowed and
    yields an empty inventory: it means no supported framework was discovered, not that the
    repository is qualified.
    """
    if discovery.truncated or discovery.state is DiscoveryState.LIMIT_EXCEEDED:
        raise InventoryError("cannot build complete inventory from truncated discovery")
    if discovery.state is DiscoveryState.MALFORMED:
        raise InventoryError("cannot build complete inventory from malformed discovery")

    links = behavior_links or {}
    evidence_by_framework = framework_evidence or DEFAULT_FRAMEWORK_EVIDENCE

    observations: list[TestCaseObservation] = []
    diagnostics: list[InventoryDiagnostic] = []
    seen_ids: set[str] = set()
    paths_to_ids: dict[str, list[str]] = {}

    for framework in sorted(discovery.frameworks, key=lambda item: item.framework):
        if framework.state is not DiscoveryState.DETECTED:
            continue
        evidence_class = evidence_by_framework.get(framework.framework)
        if evidence_class is None:
            diagnostics.append(
                InventoryDiagnostic(
                    code="unsupported-evidence-class",
                    message=f"no evidence mapping for framework {framework.framework}",
                )
            )
            continue

        for path in sorted(set(framework.test_paths)):
            test_id = stable_test_id(framework.framework, path)
            if test_id in seen_ids:
                diagnostics.append(
                    InventoryDiagnostic(
                        code="duplicate-test-id",
                        message=f"duplicate discovered test identity {test_id}",
                        test_ids=(test_id,),
                    )
                )
                continue
            seen_ids.add(test_id)
            paths_to_ids.setdefault(path, []).append(test_id)
            observations.append(
                TestCaseObservation(
                    test_id=test_id,
                    framework=framework.framework,
                    path=path,
                    behavior_ids=tuple(sorted(set(links.get(test_id, ())))),
                    evidence_class=evidence_class,
                )
            )

    for path, test_ids in sorted(paths_to_ids.items()):
        if len(test_ids) > 1:
            diagnostics.append(
                InventoryDiagnostic(
                    code="ambiguous-framework-path",
                    message=(
                        f"{path} was discovered by multiple frameworks; "
                        "the identities remain separate until the repository declares intent"
                    ),
                    test_ids=tuple(sorted(test_ids)),
                )
            )

    known_ids = {item.test_id for item in observations}
    for linked_id in sorted(set(links) - known_ids):
        diagnostics.append(
            InventoryDiagnostic(
                code="unknown-behavior-link-target",
                message=f"behavior mapping references undiscovered test {linked_id}",
                test_ids=(linked_id,),
            )
        )

    observations.sort(key=lambda item: item.test_id)
    diagnostics.sort(key=lambda item: (item.code, item.message, item.test_ids))

    return InventoryBuildResult(
        inventory=TestInventory(
            repository=repository,
            sha=sha,
            tests=tuple(observations),
        ),
        diagnostics=tuple(diagnostics),
    )
