"""Phase A core adversarial hardening (API-396).

Deterministic seeded-fuzz and fail-closed property tests against the completed
Test Platform core. Every fuzz input uses a fixed seed so the suite reproduces
exactly from a clean checkout. Nothing here requires live Jenkins, Portfolio
Graph, pilot, or provider evidence.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from test_platform.adapters.results import (
    DEFAULT_MAX_MESSAGE_CHARS,
    DEFAULT_MAX_TEST_ID_CHARS,
    ResultAdapterError,
    TestCaseResultState,
    parse_junit_xml,
    parse_nunit_xml,
)
from test_platform.analysis import HistoryObservation, assess_test_history
from test_platform.analysis.evaluator import evaluate_quality
from test_platform.contracts import (
    EvidenceClass,
    EvidenceState,
    ExecutionTarget,
    ExecutionTrustClass,
    ProfileBinding,
    ProfileRequirement,
    QualityProfile,
    QualityResult,
    RequirementLevel,
    TestValueClassification,
    TestValueFinding,
)
from test_platform.manifest import ManifestError, load_manifest
from test_platform.operator import OperatorError, parse_workflow_observations
from test_platform.planning import analyze_actions_placement
from test_platform.yaml_io import YamlContractError

SEED = 20260930
NOW = datetime(2026, 9, 30, tzinfo=UTC)
REPO = "setnessconsulting/synthetic-adversarial"
PROFILE = ProfileBinding(profile_id="python-control-plane-v1", version="1.0.0")

_JUNIT_FRAGMENTS = (
    '<testcase classname="a" name="ok"/>',
    '<testcase classname="a" name="bad"><failure message="nope"/></testcase>',
    '<testcase classname="a" name="err"><error message="boom"/></testcase>',
    '<testcase classname="a" name="skip"><skipped/></testcase>',
    '<testcase classname="a"/>',
    '<testcase name="noname-class"/>',
    "<testcase/>",
    '<testcase classname="a" name="neg" time="-3"/>',
    '<testcase classname="a" name="inf" time="inf"/>',
    '<testcase classname="a" name="nan" time="nan"/>',
    '<testcase classname="a" name="huge" time="1e308"/>',
    '<testcase classname="a" name="weird" time="not-a-number"/>',
    '<testcase classname="a" name="x\ud800broken"/>',
    '<testcase classname="a" name="newline\ninjected"/>',
    '<testcase classname="a" name="../../escape"/>',
    '<testcase classname="C:\\Users\\someone\\t" name="winpath"/>',
    "<!DOCTYPE testcase [<!ENTITY xxe SYSTEM \"file:///etc/passwd\">]>",
    "<!ENTITY xxe \"expanded\">",
    "<testcase classname=\"a\" name=\"unterminated\">",
    "</testsuite><testsuite>",
    "<testcase classname=\"a\" name=\"deep\">" * 4,
    "</testcase>" * 4,
    '<testcase classname="a" name="ATTR" data="DATA"/>',
    "gh" + "p_" + "b" * 24,
    "\x00",
    "\ufffd" * 50,
)


def _fuzz_junit(rng: random.Random) -> str:
    parts = [rng.choice(_JUNIT_FRAGMENTS) for _ in range(rng.randint(1, 12))]
    depth_open = "<testsuite>" * rng.randint(0, 30)
    depth_close = "</testsuite>" * rng.randint(0, 30)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        + depth_open
        + "<testsuite>"
        + "".join(parts)
        + "</testsuite>"
        + depth_close
    )


def test_seeded_junit_fuzz_never_escapes_typed_errors() -> None:
    rng = random.Random(SEED)
    for _ in range(300):
        document = _fuzz_junit(rng)
        try:
            parsed = parse_junit_xml(
                document, framework="pytest", max_bytes=20_000, max_cases=500
            )
        except ResultAdapterError:
            continue
        for item in parsed.tests:
            assert math.isfinite(item.duration_seconds)
            assert len(item.test_id) <= DEFAULT_MAX_TEST_ID_CHARS
            assert item.message is None or len(item.message) <= (
                DEFAULT_MAX_MESSAGE_CHARS + len("…[truncated]")
            )
        failing = any(
            item.state in {TestCaseResultState.FAIL, TestCaseResultState.ERROR}
            for item in parsed.tests
        )
        if failing:
            assert parsed.aggregate_result is QualityResult.FAIL


def test_seeded_nunit_fuzz_never_escapes_typed_errors() -> None:
    rng = random.Random(SEED + 1)
    results = ("Passed", "Failed", "Skipped", "Failed", "Bogus", "")
    for _ in range(200):
        cases = "".join(
            f'<test-case fullname="s.t{i}" result="{rng.choice(results)}" '
            f'duration="{rng.choice(["0.1", "-1", "nan", "oops"])}"/>'
            for i in range(rng.randint(0, 8))
        )
        document = f"<test-run>{cases}</test-run>"
        if rng.random() < 0.2:
            document = "<!DOCTYPE test-run>" + document
        try:
            parsed = parse_nunit_xml(
                document, max_bytes=20_000, max_cases=500
            )
        except ResultAdapterError:
            continue
        for item in parsed.tests:
            assert math.isfinite(item.duration_seconds)
            assert len(item.test_id) <= DEFAULT_MAX_TEST_ID_CHARS


def test_non_finite_and_overlong_result_fields_fail_closed() -> None:
    for bad_time in ("inf", "-inf", "nan", "Infinity", "1e999"):
        with pytest.raises(ResultAdapterError):
            parse_junit_xml(
                f'<testsuite><testcase classname="a" name="t" time="{bad_time}"/>'
                "</testsuite>",
                framework="pytest",
            )
    with pytest.raises(ResultAdapterError, match="characters"):
        parse_junit_xml(
            f'<testsuite><testcase classname="a" name="{"t" * 2000}"/>'
            "</testsuite>",
            framework="pytest",
        )
    long_message = "m" * (DEFAULT_MAX_MESSAGE_CHARS + 100)
    parsed = parse_junit_xml(
        f'<testsuite><testcase classname="a" name="t">'
        f'<failure message="{long_message}"/></testcase></testsuite>',
        framework="pytest",
    )
    assert parsed.tests[0].message is not None
    assert parsed.tests[0].message.endswith("…[truncated]")


def test_control_characters_in_test_identity_are_rejected() -> None:
    # A literal newline in an attribute is normalized to a space by XML
    # parsing; the hostile path is a character reference that resolves to a
    # control character after parsing.
    with pytest.raises(ResultAdapterError, match="control characters"):
        parse_junit_xml(
            '<testsuite><testcase classname="a" name="line&#10;break"/>'
            "</testsuite>",
            framework="pytest",
        )


def test_deeply_nested_xml_fails_closed_with_typed_error() -> None:
    document = "<testsuite>" + "<a>" * 10_000
    with pytest.raises(ResultAdapterError):
        parse_junit_xml(document, framework="pytest", max_bytes=200_000)


_MANIFEST_FRAGMENTS = (
    'profile:\n  profile_id: web-application-v1\n  version: 1.0.0\n',
    "behaviors_path: quality/behaviors.yaml\n",
    "behaviors_path: ../escape.yaml\n",
    "behaviors_path: /absolute.yaml\n",
    "suites: []\n",
    "suites:\n  - suite_id: s\n    entrypoint: verify\n    trust: pr-untrusted\n",
    "suites:\n  - suite_id: s\n    entrypoint: verify && curl x.invalid\n"
    "    trust: pr-untrusted\n",
    "suites:\n  - suite_id: s\n    entrypoint: $(rm -rf /)\n    trust: pr-untrusted\n",
    "credential: supersecret\n",
    "token: gh" + "p_" + "c" * 24 + "\n",
    "profile:\n  profile_id: invented-v1\n  version: 1.0.0\n",
    "x: [" * 40,
    "key: value: broken\n",
    "\x00: null\n",
)


def test_seeded_manifest_fuzz_never_escapes_typed_errors(tmp_path: Path) -> None:
    rng = random.Random(SEED + 2)
    token = "gh" + "p_" + "d" * 24
    for index in range(200):
        lines = ['schema_version: "1"']
        lines.extend(
            rng.choice(_MANIFEST_FRAGMENTS) for _ in range(rng.randint(1, 5))
        )
        if rng.random() < 0.25:
            lines.append(f"note: {token}\n")
        path = tmp_path / f"manifest-{index}.yaml"
        path.write_text("\n".join(lines), encoding="utf-8")
        try:
            manifest = load_manifest(path)
        except (ManifestError, YamlContractError):
            continue
        dumped = repr(manifest.model_dump(mode="json"))
        assert token not in dumped
        for suite in manifest.suites:
            assert "&&" not in suite.entrypoint
            assert "$(" not in suite.entrypoint


def test_secret_shaped_manifest_value_never_loads(tmp_path: Path) -> None:
    token = "gh" + "p_" + "e" * 24
    path = tmp_path / ".test-platform.yaml"
    path.write_text(
        "schema_version: \"1\"\n"
        "profile:\n"
        "  profile_id: web-application-v1\n"
        "  version: 1.0.0\n"
        "behaviors_path: quality/behaviors.yaml\n"
        "suites: []\n"
        f"note: prefix-{token}-suffix\n",
        encoding="utf-8",
    )
    with pytest.raises((ManifestError, YamlContractError)):
        load_manifest(path)


_OBSERVATION_FIELDS = (
    "verification",
    "deployment",
    "github_native",
    "security_native",
    "manual_fallback",
    "equivalent_plan_coverage",
    "jenkins_capable",
    "usage_complete",
    "deployment_trusted_context",
    "deployment_exact_sha",
    "deployment_verification_gate",
    "deployment_credentials_scoped",
    "deployment_readback",
    "deployment_rollback",
)


def test_seeded_workflow_observation_fuzz_fails_closed() -> None:
    rng = random.Random(SEED + 3)
    for index in range(300):
        raw: dict[str, Any] = {
            "workflow_id": f"wf-{index}",
            "evidence_intent": ["build"],
        }
        for field in _OBSERVATION_FIELDS:
            if rng.random() < 0.5:
                raw[field] = bool(rng.getrandbits(1))
        if rng.random() < 0.3:
            raw["deployment_provider_target"] = rng.choice(
                [None, "cloudflare-workers:production", "", 42]
            )
        if rng.random() < 0.2:
            raw[rng.choice(["credential", "shell", "command", "unknown_field"])] = (
                "injected"
            )
        try:
            observations = parse_workflow_observations([raw])
        except OperatorError:
            continue
        report = analyze_actions_placement(observations)
        decision = report.decisions[0]
        item = observations[0]
        if item.deployment and decision.placement.value == "move-deployment-to-jenkins":
            assert item.jenkins_capable
            assert item.equivalent_plan_coverage
            assert item.deployment_trusted_context
            assert item.deployment_exact_sha
            assert item.deployment_provider_target
            assert item.deployment_verification_gate
            assert item.deployment_credentials_scoped
            assert item.deployment_readback
            assert item.deployment_rollback


def test_credential_shaped_observation_field_is_rejected() -> None:
    with pytest.raises(OperatorError, match="unsupported fields"):
        parse_workflow_observations(
            [
                {
                    "workflow_id": "deploy",
                    "evidence_intent": ["deploy"],
                    "deployment": True,
                    "deployment_credentials": "prod-token",
                }
            ]
        )


def _profile() -> QualityProfile:
    return QualityProfile(
        profile_id="python-control-plane-v1",
        version="1.0.0",
        requirements=(
            ProfileRequirement(
                rule_id="security-negative-path",
                evidence_class=EvidenceClass.ADVERSARIAL,
                level=RequirementLevel.REQUIRED,
                description="Security boundary must have negative-path evidence.",
            ),
        ),
        allowed_trust=(ExecutionTrustClass.PR_UNTRUSTED,),
        recommended_execution=(ExecutionTarget.JENKINS,),
    )


def test_not_applicable_rule_state_cannot_become_pass() -> None:
    result = evaluate_quality(
        repository=REPO,
        sha="abcdef1234567",
        profile=_profile(),
        rule_states={"security-negative-path": EvidenceState.NOT_APPLICABLE},
        now=NOW,
    )
    assert result.result is QualityResult.NOT_EVALUABLE


def test_unknown_value_classification_is_advisory_only() -> None:
    profile = _profile()
    states = {"security-negative-path": EvidenceState.PROVEN}
    plain = evaluate_quality(
        repository=REPO,
        sha="abcdef1234567",
        profile=profile,
        rule_states=states,
        now=NOW,
    )
    finding = TestValueFinding(
        finding_id="value-unknown-1",
        test_id="pytest:tests/test_mystery.py",
        classification=TestValueClassification.UNKNOWN,
        reasons=("no behavior link observed",),
    )
    with_unknown = evaluate_quality(
        repository=REPO,
        sha="abcdef1234567",
        profile=profile,
        rule_states=states,
        test_value_findings=(finding,),
        now=NOW,
    )
    assert plain.result is QualityResult.PASS
    assert with_unknown.result is QualityResult.PASS
    assert with_unknown.test_value_findings == (finding,)


def test_skipped_only_history_is_not_evaluable() -> None:
    observation = HistoryObservation(
        test_id="pytest:tests/test_slow.py",
        sha="abcdef1234567",
        profile=PROFILE,
        suite_id="standard",
        executor="jenkins",
        trust="pr-untrusted",
        state=TestCaseResultState.SKIPPED,
        duration_seconds=1.0,
        attempt=1,
        observed_at=NOW,
    )
    assessment = assess_test_history(
        "pytest:tests/test_slow.py",
        (observation,),
        current_sha="abcdef1234567",
        current_profile=PROFILE,
    )
    assert assessment.flaky is False
    assert assessment.freshness.state is EvidenceState.NOT_EVALUABLE


def test_failure_present_with_later_pass_is_missing_not_proven() -> None:
    earlier = HistoryObservation(
        test_id="pytest:tests/test_flaky.py",
        sha="abcdef1234567",
        profile=PROFILE,
        suite_id="standard",
        executor="jenkins",
        trust="pr-untrusted",
        state=TestCaseResultState.FAIL,
        duration_seconds=1.0,
        attempt=1,
        observed_at=NOW,
    )
    later = HistoryObservation(
        test_id="pytest:tests/test_flaky.py",
        sha="abcdef1234567",
        profile=PROFILE,
        suite_id="standard",
        executor="jenkins",
        trust="pr-untrusted",
        state=TestCaseResultState.PASS,
        duration_seconds=1.0,
        attempt=2,
        observed_at=NOW,
    )
    assessment = assess_test_history(
        "pytest:tests/test_flaky.py",
        (earlier, later),
        current_sha="abcdef1234567",
        current_profile=PROFILE,
    )
    assert assessment.flaky is True
    assert assessment.freshness.state is EvidenceState.MISSING
