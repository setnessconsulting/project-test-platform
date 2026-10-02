from __future__ import annotations

import pytest

from test_platform.contracts import (
    EvidenceClass,
    ExecutionTrustClass,
    TrustCapability,
)
from test_platform.trust import (
    TrustPolicyError,
    evaluate_capabilities,
    require_evidence_allowed_for_trust,
    require_live_qualification_context,
)


def test_untrusted_pr_cannot_request_provider_credentials() -> None:
    decision = evaluate_capabilities(
        ExecutionTrustClass.PR_UNTRUSTED,
        (TrustCapability.TEST_EXECUTION, TrustCapability.BOUNDED_PROVIDER_CREDENTIALS),
    )

    assert decision.allowed is False
    assert decision.denied == (TrustCapability.BOUNDED_PROVIDER_CREDENTIALS,)


def test_trusted_manual_still_cannot_read_live_provider() -> None:
    decision = evaluate_capabilities(
        ExecutionTrustClass.TRUSTED_MANUAL,
        (TrustCapability.LIVE_PROVIDER_READ,),
    )

    assert decision.allowed is False


def test_live_qualification_requires_exact_sha_target_and_owner_approval() -> None:
    require_live_qualification_context(
        trust=ExecutionTrustClass.LIVE_QUALIFICATION,
        sha="a" * 40,
        target="fixture:test",
        owner_approved=True,
    )

    # A short, non-hex, or traversal-shaped revision cannot authorise live work.
    for bad_sha in ("abc123", "a" * 39, "../../etc", "A" * 40):
        with pytest.raises(TrustPolicyError, match="full exact"):
            require_live_qualification_context(
                trust=ExecutionTrustClass.LIVE_QUALIFICATION,
                sha=bad_sha,
                target="fixture:test",
                owner_approved=True,
            )

    with pytest.raises(TrustPolicyError, match="owner approval"):
        require_live_qualification_context(
            trust=ExecutionTrustClass.LIVE_QUALIFICATION,
            sha="a" * 40,
            target="fixture:test",
            owner_approved=False,
        )


def test_lower_trust_cannot_claim_live_qualification_evidence() -> None:
    with pytest.raises(TrustPolicyError, match="live-qualification evidence"):
        require_evidence_allowed_for_trust(
            ExecutionTrustClass.PR_UNTRUSTED,
            (EvidenceClass.STATIC, EvidenceClass.LIVE),
        )


def test_live_trust_can_claim_live_qualification_evidence() -> None:
    require_evidence_allowed_for_trust(
        ExecutionTrustClass.LIVE_QUALIFICATION,
        (EvidenceClass.LIVE,),
    )
