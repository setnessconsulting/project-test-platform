"""Bounded test-result adapters for common framework interchange formats."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from xml.etree import ElementTree

from test_platform.contracts import QualityResult

DEFAULT_MAX_RESULT_BYTES = 2_000_000
DEFAULT_MAX_TEST_CASES = 10_000


class ResultAdapterError(ValueError):
    """Raised when a result document is malformed, unsafe, or exceeds configured bounds."""


class TestCaseResultState(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass(frozen=True)
class AdapterTestResult:
    """Executor-neutral per-test result used by later history/receipt layers."""

    test_id: str
    framework: str
    state: TestCaseResultState
    duration_seconds: float
    attempt: int = 1
    message: str | None = None


@dataclass(frozen=True)
class ParsedTestResults:
    """Bounded parse result preserving every observed attempt."""

    framework: str
    tests: tuple[AdapterTestResult, ...]

    @property
    def aggregate_result(self) -> QualityResult:
        failing = {TestCaseResultState.FAIL, TestCaseResultState.ERROR}
        if any(item.state in failing for item in self.tests):
            return QualityResult.FAIL
        return QualityResult.PASS


def _bounded_xml(content: str | bytes, *, max_bytes: int) -> str:
    raw = content.encode("utf-8") if isinstance(content, str) else content
    if len(raw) > max_bytes:
        raise ResultAdapterError(f"result document exceeds {max_bytes} bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ResultAdapterError("result document must be UTF-8") from exc

    upper = text.upper()
    if "<!DOCTYPE" in upper or "<!ENTITY" in upper:
        raise ResultAdapterError("DTD/entity declarations are not allowed in test results")
    return text


def _duration(value: str | None) -> float:
    if value is None or value == "":
        return 0.0
    try:
        duration = float(value)
    except ValueError as exc:
        raise ResultAdapterError(f"invalid test duration {value!r}") from exc
    if duration < 0:
        raise ResultAdapterError("test duration cannot be negative")
    return duration


def _stable_case_id(framework: str, classname: str | None, name: str | None) -> str:
    candidate = "::".join(part for part in (classname, name) if part)
    if not candidate:
        raise ResultAdapterError("test case is missing both classname and name")
    return f"{framework}:{candidate}"


def _attempts(
    results: list[tuple[str, TestCaseResultState, float, str | None]],
    framework: str,
) -> tuple[AdapterTestResult, ...]:
    counts: dict[str, int] = {}
    normalized: list[AdapterTestResult] = []
    for test_id, state, duration, message in results:
        counts[test_id] = counts.get(test_id, 0) + 1
        normalized.append(
            AdapterTestResult(
                test_id=test_id,
                framework=framework,
                state=state,
                duration_seconds=duration,
                attempt=counts[test_id],
                message=message,
            )
        )
    return tuple(normalized)


def parse_junit_xml(
    content: str | bytes,
    *,
    framework: str,
    max_bytes: int = DEFAULT_MAX_RESULT_BYTES,
    max_cases: int = DEFAULT_MAX_TEST_CASES,
) -> ParsedTestResults:
    """Parse JUnit XML without resolving external entities or executing repository code."""
    text = _bounded_xml(content, max_bytes=max_bytes)
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise ResultAdapterError("malformed JUnit XML") from exc

    cases = root.findall(".//testcase")
    if len(cases) > max_cases:
        raise ResultAdapterError(f"result document exceeds {max_cases} test cases")

    raw: list[tuple[str, TestCaseResultState, float, str | None]] = []
    for case in cases:
        test_id = _stable_case_id(framework, case.get("classname"), case.get("name"))
        duration = _duration(case.get("time"))
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        if error is not None:
            state = TestCaseResultState.ERROR
            message = error.get("message")
        elif failure is not None:
            state = TestCaseResultState.FAIL
            message = failure.get("message")
        elif skipped is not None:
            state = TestCaseResultState.SKIPPED
            message = skipped.get("message")
        else:
            state = TestCaseResultState.PASS
            message = None
        raw.append((test_id, state, duration, message))

    return ParsedTestResults(framework=framework, tests=_attempts(raw, framework))


def parse_nunit_xml(
    content: str | bytes,
    *,
    framework: str = "pester",
    max_bytes: int = DEFAULT_MAX_RESULT_BYTES,
    max_cases: int = DEFAULT_MAX_TEST_CASES,
) -> ParsedTestResults:
    """Parse the bounded NUnit-style test-case format commonly emitted by Pester."""
    text = _bounded_xml(content, max_bytes=max_bytes)
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise ResultAdapterError("malformed NUnit XML") from exc

    cases = root.findall(".//test-case")
    if len(cases) > max_cases:
        raise ResultAdapterError(f"result document exceeds {max_cases} test cases")

    raw: list[tuple[str, TestCaseResultState, float, str | None]] = []
    for case in cases:
        name = case.get("fullname") or case.get("name")
        test_id = _stable_case_id(framework, None, name)
        duration = _duration(case.get("duration") or case.get("time"))
        result = (case.get("result") or "").strip().lower()
        if result in {"passed", "success"}:
            state = TestCaseResultState.PASS
        elif result in {"skipped", "ignored", "inconclusive"}:
            state = TestCaseResultState.SKIPPED
        elif result in {"failed", "failure"}:
            state = TestCaseResultState.FAIL
        else:
            state = TestCaseResultState.ERROR
        reason = case.find(".//message")
        message = reason.text.strip() if reason is not None and reason.text else None
        raw.append((test_id, state, duration, message))

    return ParsedTestResults(framework=framework, tests=_attempts(raw, framework))


@dataclass(frozen=True)
class JUnitFrameworkAdapter:
    """Small named adapter for frameworks configured to emit JUnit XML."""

    framework: str

    def parse(self, content: str | bytes) -> ParsedTestResults:
        return parse_junit_xml(content, framework=self.framework)


PYTEST_ADAPTER = JUnitFrameworkAdapter("pytest")
JEST_ADAPTER = JUnitFrameworkAdapter("jest")
VITEST_ADAPTER = JUnitFrameworkAdapter("vitest")
PLAYWRIGHT_ADAPTER = JUnitFrameworkAdapter("playwright")


@dataclass(frozen=True)
class PesterResultAdapter:
    framework: str = "pester"

    def parse_junit(self, content: str | bytes) -> ParsedTestResults:
        return parse_junit_xml(content, framework=self.framework)

    def parse_nunit(self, content: str | bytes) -> ParsedTestResults:
        return parse_nunit_xml(content, framework=self.framework)


PESTER_ADAPTER = PesterResultAdapter()
