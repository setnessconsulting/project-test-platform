from __future__ import annotations

import pytest

from test_platform.contracts import ExecutionTrustClass, TrustCapability
from test_platform.trust import (
    TrustPolicyError,
    evaluate_capabilities,
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

    with pytest.raises(TrustPolicyError, match="full exact"):
        require_live_qualification_context(
            trust=ExecutionTrustClass.LIVE_QUALIFICATION,
            sha="abcdef1",
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
