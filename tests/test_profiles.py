from __future__ import annotations

from test_platform.contracts import EvidenceClass, RequirementLevel
from test_platform.profiles import PROFILE_FILES, load_all_profiles, load_profile


def test_all_initial_profiles_load_with_explicit_policy() -> None:
    profiles = load_all_profiles()

    assert len(profiles) == 8
    assert {profile.profile_id for profile in profiles} == set(PROFILE_FILES)
    assert all(profile.allowed_trust for profile in profiles)
    assert all(profile.recommended_execution for profile in profiles)
    assert all(profile.requirements for profile in profiles)


def test_browser_game_requires_critical_e2e_evidence() -> None:
    profile = load_profile("browser-game-v1")

    assert profile.critical_journey_e2e_required is True
    assert any(
        requirement.evidence_class is EvidenceClass.E2E
        and requirement.level is RequirementLevel.REQUIRED
        for requirement in profile.requirements
    )


def test_documentation_tool_does_not_require_mutation_analysis() -> None:
    profile = load_profile("documentation-tool-v1")

    assert profile.mutation_analysis is RequirementLevel.NOT_APPLICABLE
