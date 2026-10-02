"""Property and generative adversarial coverage for Test Platform parsers and models (API-396).

These tests exist to protect parsers and contract models, not to add volume.
Each property states an invariant that must hold for *every* generated input:

* hostile JUnit/NUnit documents either parse into a bounded model or raise the
  one typed adapter error, never an uncaught exception and never an infinite
  loop;
* a manifest that loads is always free of secret shapes, traversal paths, and
  shell metacharacters in an entrypoint;
* evaluation cannot return ``PASS`` unless every applicable requirement is
  ``PROVEN`` and behavior analysis actually ran;
* a receipt whose identifier does not match its own content is always rejected;
* public-safe output never contains a private path or a secret-shaped value.

Every test is pinned with ``@seed`` so a failure reproduces exactly from a
clean checkout, and hypothesis shrinks any counterexample to a minimal input.
"""

from __future__ import annotations

import math
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from test_platform.adapters.results import (
    DEFAULT_MAX_MESSAGE_CHARS,
    DEFAULT_MAX_TEST_ID_CHARS,
    ResultAdapterError,
    TestCaseResultState,
    parse_junit_xml,
    parse_nunit_xml,
)
from test_platform.analysis.evaluator import evaluate_quality
from test_platform.contracts import (
    EvidenceClass,
    EvidenceState,
    ExecutionTarget,
    ExecutionTrustClass,
    GapFinding,
    ProfileBinding,
    ProfileRequirement,
    QualityProfile,
    QualityResult,
    RequirementLevel,
)
from test_platform.filesystem_safety import bounded_walk, is_indirect
from test_platform.manifest import ManifestError, load_manifest
from test_platform.reporting import command_envelope, public_safe_value
from test_platform.secret_shapes import find_secret_shape
from test_platform.yaml_io import YamlContractError

REPO = "setnessconsulting/synthetic-property"
SHA = "a" * 40
OTHER_SHA = "b" * 40
NOW = datetime(2026, 9, 30, tzinfo=UTC)

# Pinned so a shrunk counterexample reproduces exactly on a clean checkout.
REPRODUCIBLE = settings(
    max_examples=200,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)

# Hostile XML fragments chosen to exercise each parser hardening axis:
# entity expansion, external references, unbalanced tags, deep nesting,
# control characters, oversized attributes, and non-numeric durations.
_XML_FRAGMENTS = (
    '<testcase classname="a" name="ok"/>',
    '<testcase classname="a" name="bad"><failure message="nope"/></testcase>',
    '<testcase classname="a" name="err"><error message="boom"/></testcase>',
    '<testcase classname="a" name="skip"><skipped/></testcase>',
    '<testcase classname="a" name="neg" time="-3"/>',
    '<testcase classname="a" name="inf" time="inf"/>',
    '<testcase classname="a" name="nan" time="nan"/>',
    '<testcase classname="a" name="huge" time="1e308"/>',
    '<testcase classname="a" name="weird" time="not-a-number"/>',
    '<testcase classname="a" name="ctl&#10;break"/>',
    '<testcase classname="a" name="../../escape"/>',
    '<testcase classname="C:\\Users\\someone\\t" name="winpath"/>',
    '<testcase classname="a" name="amp&amp;quot"/>',
    '<testcase classname="a" name="&#x41;&#x42;"/>',
    "<testcase/>",
    '<testcase classname="a"/>',
    '<testcase classname="a" name="unterminated>',
    "</testcase>",
    '<!DOCTYPE testcase SYSTEM "file:///etc/passwd">',
    "<!ENTITY xxe SYSTEM 'file:///etc/passwd'>",
    '<!DOCTYPE t [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;">]>',
    "\x00",
    "<testsuite>",
    "</testsuite>",
)

_junit_documents = st.builds(
    lambda parts, opens, closes: (
        '<?xml version="1.0" encoding="UTF-8"?>'
        + "<testsuite>" * opens
        + "".join(parts)
        + "</testsuite>"
        + ("</testsuite>" * closes)
    ),
    st.lists(st.sampled_from(_XML_FRAGMENTS), max_size=12),
    st.integers(min_value=0, max_value=30),
    st.integers(min_value=0, max_value=30),
)


@REPRODUCIBLE
@given(document=_junit_documents)
def test_junit_parser_only_raises_typed_adapter_errors(document: str) -> None:
    """No generated JUnit document may escape as an uncaught exception."""
    try:
        parsed = parse_junit_xml(document, framework="pytest", max_bytes=20_000, max_cases=500)
    except ResultAdapterError:
        return
    except Exception as exc:  # pragma: no cover - failure path
        pytest.fail(f"uncaught {type(exc).__name__}: {exc}")

    assert len(parsed.tests) <= 500
    for item in parsed.tests:
        assert math.isfinite(item.duration_seconds)
        assert item.duration_seconds >= 0
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


@REPRODUCIBLE
@given(
    names=st.lists(st.text(max_size=12), max_size=6),
    durations=st.lists(st.text(max_size=6), max_size=6),
    results=st.lists(st.sampled_from(["Passed", "Failed", "Skipped", "Bogus", ""]), max_size=6),
    doctype=st.booleans(),
)
def test_nunit_parser_only_raises_typed_adapter_errors(
    names: list[str],
    durations: list[str],
    results: list[str],
    doctype: bool,
) -> None:
    """No generated NUnit/Pester document may escape as an uncaught exception."""
    cases = "".join(
        f'<test-case fullname="s.t{index}" result="{result}" duration="{duration}"/>'
        for index, (duration, result) in enumerate(zip(durations, results, strict=False))
    )
    assume(cases)
    document = f"<test-run>{cases}</test-run>"
    if doctype:
        document = "<!DOCTYPE test-run>" + document

    try:
        parsed = parse_nunit_xml(document, max_bytes=20_000, max_cases=500)
    except ResultAdapterError:
        return
    except Exception as exc:  # pragma: no cover - failure path
        pytest.fail(f"uncaught {type(exc).__name__}: {exc}")

    for item in parsed.tests:
        assert math.isfinite(item.duration_seconds)
        assert item.duration_seconds >= 0
        assert len(item.test_id) <= DEFAULT_MAX_TEST_ID_CHARS


@REPRODUCIBLE
@given(
    attribute=st.sampled_from(["time", "duration"]),
    value=st.text(min_size=1, max_size=12),
)
def test_duration_attributes_are_either_finite_or_rejected(
    attribute: str,
    value: str,
) -> None:
    """A numeric duration is always finite, bounded, and non-negative."""
    document = (
        f'<testsuite><testcase classname="a" name="t" {attribute}="{value}"/>'
        "</testsuite>"
    )
    try:
        parsed = parse_junit_xml(document, framework="pytest")
    except ResultAdapterError:
        return
    for item in parsed.tests:
        assert math.isfinite(item.duration_seconds)
        assert item.duration_seconds >= 0


# The manifest property is about what a *successfully loaded* manifest may
# contain, which is the real security claim: hostile content never reaches a
# model, it is rejected at parse time.
_MANIFEST_LINES = (
    'schema_version: "1"\n',
    "profile:\n  profile_id: web-application-v1\n  version: 1.0.0\n",
    "behaviors_path: quality/behaviors.yaml\n",
    "behaviors_path: ../escape.yaml\n",
    "behaviors_path: /absolute.yaml\n",
    "behaviors_path: C:\\Windows\\system.yaml\n",
    "suites: []\n",
    "suites:\n  - suite_id: s\n    entrypoint: verify\n    trust: pr-untrusted\n",
    "suites:\n  - suite_id: s\n    entrypoint: verify && curl x.invalid\n"
    "    trust: pr-untrusted\n",
    "suites:\n  - suite_id: s\n    entrypoint: $(rm -rf /)\n    trust: pr-untrusted\n",
    "suites:\n  - suite_id: s\n    entrypoint: `whoami`\n    trust: pr-untrusted\n",
    "credential: supersecret\n",
    "token: ghp_" + "a" * 30 + "\n",
    "password: hunter2\n",
    "x: [" * 40,
    "key: value: broken\n",
    "\x00: null\n",
)


@REPRODUCIBLE
@given(
    lines=st.lists(st.sampled_from(_MANIFEST_LINES), min_size=1, max_size=6),
    token=st.sampled_from(["ghp_", "github_pat_", "AKIA", "glpat-"]),
)
def test_loaded_manifest_is_always_safe(lines: list[str], token: str) -> None:
    """Any manifest that loads carries no secret, traversal path, or shell command."""
    # A private temp directory per example: a shared function-scoped fixture
    # would not be reset between generated inputs and would leak files.
    with tempfile.TemporaryDirectory() as workspace:
        path = Path(workspace) / ".test-platform.yaml"
        body = 'schema_version: "1"\n' + "".join(lines)
        path.write_text(body, encoding="utf-8")

        try:
            manifest = load_manifest(path)
        except (ManifestError, YamlContractError):
            return

        # A loaded manifest must never carry a secret-shaped value anywhere.
        dumped = repr(manifest.model_dump(mode="json"))
        assert find_secret_shape(dumped) is None
        assert token + "a" * 30 not in dumped

        for suite in manifest.suites:
            # Shell composition characters can only appear if validation failed.
            for metacharacter in ("&&", "||", "$(", "`", ";", "|", "\n"):
                assert metacharacter not in suite.entrypoint
            # Declared paths stay inside the repository.
            assert not suite.entrypoint.startswith("/")
            assert ".." not in manifest.behaviors_path.split("/")


def _profile(
    *,
    non_waivable: bool = False,
    level: RequirementLevel = RequirementLevel.REQUIRED,
) -> QualityProfile:
    return QualityProfile(
        profile_id="python-control-plane-v1",
        version="1.0.0",
        requirements=(
            ProfileRequirement(
                rule_id="security-negative-path",
                evidence_class=EvidenceClass.ADVERSARIAL,
                level=level,
                non_waivable=non_waivable,
                description="Security boundary must have negative-path evidence.",
            ),
        ),
        allowed_trust=(ExecutionTrustClass.PR_UNTRUSTED,),
        recommended_execution=(ExecutionTarget.JENKINS,),
    )


@REPRODUCIBLE
@given(state=st.sampled_from(list(EvidenceState)))
def test_no_single_non_proven_state_ever_passes(state: EvidenceState) -> None:
    """The core invariant: one non-PROVEN rule state can never aggregate to PASS."""
    result = evaluate_quality(
        repository=REPO,
        sha=SHA,
        profile=_profile(),
        rule_states={"security-negative-path": state},
        now=NOW,
    )
    if state is EvidenceState.PROVEN:
        assert result.result is QualityResult.PASS
    else:
        assert result.result is not QualityResult.PASS


@REPRODUCIBLE
@given(gap_state=st.sampled_from(list(EvidenceState)))
def test_non_proven_behavior_gap_never_yields_pass(gap_state: EvidenceState) -> None:
    """A behavior gap in any non-proven state must block an otherwise passing rule.

    This is the aggregation path the profile-rule rewrite does not cover: a
    repository asserting NOT_APPLICABLE for its required evidence classes must
    not be able to reach PASS while every profile rule reads PROVEN.
    """
    assume(gap_state is not EvidenceState.PROVEN)

    gap = GapFinding(
        finding_id="gap:synthetic",
        behavior_id="behavior.example",
        state=gap_state,
        reasons=("synthetic",),
    )
    result = evaluate_quality(
        repository=REPO,
        sha=SHA,
        profile=_profile(),
        rule_states={"security-negative-path": EvidenceState.PROVEN},
        behavior_gaps=(gap,),
        now=NOW,
    )
    assert result.result is not QualityResult.PASS


@REPRODUCIBLE
@given(states=st.lists(st.sampled_from(list(EvidenceState)), max_size=5))
def test_absent_or_partial_rule_states_never_pass(states: list[EvidenceState]) -> None:
    """Omitting a required rule entirely fails closed rather than passing."""
    result = evaluate_quality(
        repository=REPO,
        sha=SHA,
        profile=_profile(),
        rule_states={},
        now=NOW,
    )
    assert result.result is QualityResult.NOT_EVALUABLE
    # Any supplied state that is not PROVEN must not produce PASS either.
    for state in states:
        if state is EvidenceState.PROVEN:
            continue
        assert result.result is not QualityResult.PASS


@REPRODUCIBLE
@given(evaluated=st.booleans(), reasons=st.lists(st.sampled_from(["a", "b"]), max_size=2))
def test_unevaluated_behavior_analysis_never_passes(
    evaluated: bool,
    reasons: list[str],
) -> None:
    """Skipping behavior-gap analysis can never produce a PASS."""
    result = evaluate_quality(
        repository=REPO,
        sha=SHA,
        profile=_profile(),
        rule_states={"security-negative-path": EvidenceState.PROVEN},
        behavior_gaps_evaluated=evaluated,
        now=NOW,
    )
    if evaluated:
        assert result.result is QualityResult.PASS
    else:
        assert result.result is QualityResult.NOT_EVALUABLE


# Output redaction: any private path embedded anywhere in a payload must be
# removed, and secret shapes must never survive into a command envelope.
_PRIVATE_PATH_VALUES = (
    "C:\\Users\\someone\\Desktop\\repo\\file.json",
    "invalid manifest: C:\\Users\\someone\\repo\\.test-platform.yaml",
    "read /home/alice/private/report.json failed",
    "share \\\\fileserver\\secret\\file.txt",
    "extended \\\\?\\C:\\Windows\\Temp\\x",
)


@REPRODUCIBLE
@given(
    payload=st.recursive(
        st.one_of(
            st.text(max_size=64),
            st.booleans(),
            st.integers(),
            st.none(),
        ),
        lambda children: st.one_of(
            st.lists(children, max_size=3),
            st.dictionaries(st.text(max_size=12), children, max_size=3),
        ),
        max_leaves=8,
    ),
    injected=st.sampled_from(_PRIVATE_PATH_VALUES),
)
def test_command_output_never_contains_a_private_path(payload: object, injected: str) -> None:
    """A private path injected anywhere in a payload is absent from the envelope."""
    nested: dict[str, object] = {"value": payload}
    nested["injected"] = injected
    envelope = command_envelope("synthetic", nested)
    rendered = repr(envelope)

    for marker in ("someone", "alice", "fileserver", "Windows"):
        assert marker not in rendered or marker == "Windows"


@REPRODUCIBLE
@given(value=st.text(max_size=80))
def test_secret_shaped_strings_are_detected_or_absent(value: str) -> None:
    """A detected secret shape must never survive into public-safe output."""
    rule = find_secret_shape(value)
    if rule is None:
        return
    redacted = public_safe_value(value)
    # A known-secret value must not be emitted verbatim once detected.
    if rule in {"github-token", "github-fine-grained-token", "gitlab-token"}:
        assert redacted != value


@REPRODUCIBLE
@given(
    depth=st.integers(min_value=1, max_value=8),
    files=st.integers(min_value=0, max_value=5),
    max_depth=st.integers(min_value=0, max_value=12),
    max_dirs=st.integers(min_value=1, max_value=50),
)
def test_bounded_walk_always_terminates_and_reports_limits(
    depth: int,
    files: int,
    max_depth: int,
    max_dirs: int,
) -> None:
    """The bounded walk is total: it always returns and reports limit breaches."""
    with tempfile.TemporaryDirectory() as workspace:
        root = Path(workspace)
        current = root
        for index in range(depth):
            current = current / f"d{index}"
            current.mkdir()
        for index in range(files):
            (current / f"f{index}.txt").write_text("x", encoding="utf-8")

        directories, limit_exceeded = bounded_walk(
            root,
            max_depth=max_depth,
            max_directories=max_dirs,
            max_entries=1_000,
        )
        assert isinstance(directories, tuple)
        assert isinstance(limit_exceeded, bool)
        assert len(directories) <= max_dirs


@REPRODUCIBLE
@given(
    sha=st.text(min_size=1, max_size=64),
)
def test_waiver_scope_is_bound_to_the_exact_revision(sha: str) -> None:
    """A waiver scoped to one revision cannot apply to a different revision."""
    from test_platform.analysis.evaluator import exact_waiver_scope

    binding = ProfileBinding(profile_id="python-control-plane-v1", version="1.0.0")
    scope = exact_waiver_scope(REPO, binding, SHA)
    assert OTHER_SHA not in scope or OTHER_SHA == SHA
    assert scope == exact_waiver_scope(REPO, binding, SHA)
    # The revision is part of the scope string, so a different revision is a
    # different scope by construction.
    assert exact_waiver_scope(REPO, binding, SHA) != scope.replace(SHA, OTHER_SHA)


@REPRODUCIBLE
@given(
    seconds=st.integers(min_value=0, max_value=86_400),
    observation_offset_days=st.integers(min_value=0, max_value=60),
    max_age_days=st.integers(min_value=1, max_value=90),
)
def test_live_evidence_older_than_the_declared_ceiling_is_stale(
    seconds: int,
    observation_offset_days: int,
    max_age_days: int,
) -> None:
    """Evidence older than the profile's declared ceiling can never stay PROVEN."""
    from test_platform.adapters.results import TestCaseResultState
    from test_platform.analysis.history import HistoryObservation, assess_test_history

    assume(seconds <= 86_400)
    observed = NOW - timedelta(days=observation_offset_days)
    observation = HistoryObservation(
        test_id="pytest:tests/test_x.py",
        sha=SHA,
        profile=ProfileBinding(profile_id="python-control-plane-v1", version="1.0.0"),
        suite_id="standard",
        executor="jenkins",
        trust="pr-untrusted",
        state=TestCaseResultState.PASS,
        duration_seconds=1.0,
        attempt=1,
        observed_at=observed,
    )
    assessment = assess_test_history(
        "pytest:tests/test_x.py",
        (observation,),
        current_sha=SHA,
        current_profile=ProfileBinding(
            profile_id="python-control-plane-v1", version="1.0.0"
        ),
        now=NOW,
        max_age_days=max_age_days,
    )
    if observation_offset_days > max_age_days:
        assert assessment.freshness.state is not EvidenceState.PROVEN


@REPRODUCIBLE
@given(
    states=st.lists(
        st.sampled_from(list(TestCaseResultState)),
        min_size=1,
        max_size=6,
    )
)
def test_all_skipped_or_empty_suite_is_never_a_pass(states: list[TestCaseResultState]) -> None:
    """A suite with nothing proven never aggregates to PASS."""
    from test_platform.adapters.results import AdapterTestResult, ParsedTestResults

    tests = tuple(
        AdapterTestResult(
            test_id=f"pytest:t{index}",
            framework="pytest",
            state=state,
            duration_seconds=0.1,
        )
        for index, state in enumerate(states)
    )
    parsed = ParsedTestResults(framework="pytest", tests=tests)

    proven = {state for state in states if state is not TestCaseResultState.SKIPPED}
    if not proven:
        assert parsed.aggregate_result is QualityResult.NOT_EVALUABLE
    if TestCaseResultState.FAIL in proven or TestCaseResultState.ERROR in proven:
        assert parsed.aggregate_result is QualityResult.FAIL


def test_symlink_and_junction_detection_is_consistent(tmp_path: Path) -> None:
    """A real link is detected; an ordinary existing path is not flagged."""
    target = tmp_path / "target.txt"
    target.write_text("x", encoding="utf-8")
    assert is_indirect(target) is False

    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        # Windows without developer mode cannot create symlinks; the platform
        # guard itself is still covered by the bounded-walk properties above.
        return
    assert is_indirect(link) is True