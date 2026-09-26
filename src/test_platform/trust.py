"""Execution trust policy for credential-safe planning and qualification."""

from __future__ import annotations

import re

from test_platform.contracts import (
    ExecutionTrustClass,
    TrustCapability,
    TrustPolicyDecision,
)

_EXACT_SHA = re.compile(r"^[0-9a-f]{40,64}$")

TRUST_CAPABILITIES: dict[ExecutionTrustClass, frozenset[TrustCapability]] = {
    ExecutionTrustClass.PR_UNTRUSTED: frozenset(
        {
            TrustCapability.REPOSITORY_READ,
            TrustCapability.TEST_EXECUTION,
            TrustCapability.SYNTHETIC_FIXTURES,
        }
    ),
    ExecutionTrustClass.TRUSTED_BRANCH: frozenset(
        {
            TrustCapability.REPOSITORY_READ,
            TrustCapability.TEST_EXECUTION,
            TrustCapability.SYNTHETIC_FIXTURES,
            TrustCapability.PRIVATE_EVIDENCE_WRITE,
        }
    ),
    ExecutionTrustClass.TRUSTED_MANUAL: frozenset(
        {
            TrustCapability.REPOSITORY_READ,
            TrustCapability.TEST_EXECUTION,
            TrustCapability.SYNTHETIC_FIXTURES,
            TrustCapability.PRIVATE_EVIDENCE_WRITE,
            TrustCapability.BOUNDED_TEST_CREDENTIALS,
        }
    ),
    ExecutionTrustClass.LIVE_QUALIFICATION: frozenset(
        {
            TrustCapability.REPOSITORY_READ,
            TrustCapability.TEST_EXECUTION,
            TrustCapability.SYNTHETIC_FIXTURES,
            TrustCapability.PRIVATE_EVIDENCE_WRITE,
            TrustCapability.BOUNDED_TEST_CREDENTIALS,
            TrustCapability.BOUNDED_PROVIDER_CREDENTIALS,
            TrustCapability.LIVE_PROVIDER_READ,
        }
    ),
}


class TrustPolicyError(ValueError):
    """Raised when an execution request violates the trust policy."""


def evaluate_capabilities(
    trust: ExecutionTrustClass,
    requested: tuple[TrustCapability, ...],
) -> TrustPolicyDecision:
    """Evaluate requested capabilities without escalating the supplied trust class."""
    available = TRUST_CAPABILITIES[trust]
    denied = tuple(capability for capability in requested if capability not in available)
    return TrustPolicyDecision(
        trust=trust,
        requested=requested,
        allowed=not denied,
        denied=denied,
        reason="all requested capabilities allowed" if not denied else "capability denied by trust class",
    )


def require_live_qualification_context(
    *,
    trust: ExecutionTrustClass,
    sha: str,
    target: str,
    owner_approved: bool,
) -> None:
    """Require exact trusted context before any live qualification can be planned."""
    if trust is not ExecutionTrustClass.LIVE_QUALIFICATION:
        raise TrustPolicyError("live qualification requires live-qualification trust")
    if not _EXACT_SHA.fullmatch(sha):
        raise TrustPolicyError("live qualification requires a full exact repository SHA")
    if not target.strip():
        raise TrustPolicyError("live qualification requires an explicit target")
    if not owner_approved:
        raise TrustPolicyError("live qualification requires explicit owner approval")
