from __future__ import annotations

import pytest

from test_platform.adapters.results import (
    JEST_ADAPTER,
    PESTER_ADAPTER,
    PLAYWRIGHT_ADAPTER,
    PYTEST_ADAPTER,
    VITEST_ADAPTER,
    ResultAdapterError,
    TestCaseResultState,
    parse_junit_xml,
)
from test_platform.contracts import QualityResult


JUNIT = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite tests="4">
  <testcase classname="sample.Policy" name="allows valid target" time="0.10"/>
  <testcase classname="sample.Policy" name="rejects stale target" time="0.20">
    <failure message="expected rejection"/>
  </testcase>
  <testcase classname="sample.Policy" name="temporarily unavailable" time="0.01">
    <skipped message="fixture offline"/>
  </testcase>
  <testcase classname="sample.Policy" name="provider error" time="0.02">
    <error message="provider failed"/>
  </testcase>
</testsuite>
"""


def test_junit_normalization_preserves_states_and_duration() -> None:
    parsed = parse_junit_xml(JUNIT, framework="pytest")

    assert parsed.aggregate_result is QualityResult.FAIL
    assert [item.state for item in parsed.tests] == [
        TestCaseResultState.PASS,
        TestCaseResultState.FAIL,
        TestCaseResultState.SKIPPED,
        TestCaseResultState.ERROR,
    ]
    assert parsed.tests[0].test_id == "pytest:sample.Policy::allows valid target"
    assert parsed.tests[0].duration_seconds == 0.10


@pytest.mark.parametrize(
    "adapter,framework",
    [
        (PYTEST_ADAPTER, "pytest"),
        (JEST_ADAPTER, "jest"),
        (VITEST_ADAPTER, "vitest"),
        (PLAYWRIGHT_ADAPTER, "playwright"),
    ],
)
def test_named_junit_adapters_use_common_result_model(adapter: object, framework: str) -> None:
    parsed = adapter.parse(JUNIT)  # type: ignore[attr-defined]
    assert parsed.framework == framework
    assert parsed.tests[0].framework == framework


def test_duplicate_test_ids_preserve_attempt_sequence_for_later_flake_analysis() -> None:
    content = """<testsuite>
      <testcase classname="a" name="retry" time="0.1"><failure/></testcase>
      <testcase classname="a" name="retry" time="0.1"/>
    </testsuite>"""

    parsed = parse_junit_xml(content, framework="vitest")

    assert [item.attempt for item in parsed.tests] == [1, 2]
    assert [item.state for item in parsed.tests] == [
        TestCaseResultState.FAIL,
        TestCaseResultState.PASS,
    ]
    assert parsed.aggregate_result is QualityResult.FAIL


def test_doctype_and_entities_are_rejected_before_xml_parse() -> None:
    malicious = """<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
    <testsuite><testcase name="&xxe;"/></testsuite>"""

    with pytest.raises(ResultAdapterError, match="DTD/entity"):
        parse_junit_xml(malicious, framework="pytest")


def test_result_size_and_case_count_are_bounded() -> None:
    with pytest.raises(ResultAdapterError, match="bytes"):
        parse_junit_xml("<testsuite/>" * 100, framework="pytest", max_bytes=20)

    many = "<testsuite>" + "".join(
        f'<testcase classname="c" name="t{i}"/>' for i in range(3)
    ) + "</testsuite>"
    with pytest.raises(ResultAdapterError, match="test cases"):
        parse_junit_xml(many, framework="pytest", max_cases=2)


def test_malformed_or_negative_duration_fails_closed() -> None:
    with pytest.raises(ResultAdapterError, match="malformed"):
        parse_junit_xml("<testsuite>", framework="pytest")

    with pytest.raises(ResultAdapterError, match="negative"):
        parse_junit_xml(
            '<testsuite><testcase classname="a" name="b" time="-1"/></testsuite>',
            framework="pytest",
        )


def test_pester_nunit_adapter_normalizes_results() -> None:
    nunit = """<test-run>
      <test-case fullname="suite.pass" result="Passed" duration="0.2"/>
      <test-case fullname="suite.skip" result="Skipped" duration="0.1"/>
      <test-case fullname="suite.fail" result="Failed" duration="0.3">
        <failure><message>boom</message></failure>
      </test-case>
    </test-run>"""

    parsed = PESTER_ADAPTER.parse_nunit(nunit)

    assert parsed.framework == "pester"
    assert [item.state for item in parsed.tests] == [
        TestCaseResultState.PASS,
        TestCaseResultState.SKIPPED,
        TestCaseResultState.FAIL,
    ]
    assert parsed.aggregate_result is QualityResult.FAIL
