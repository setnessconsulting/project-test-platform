"""Bounded test-result adapters for common framework interchange formats."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from xml.etree import ElementTree

from test_platform.contracts import QualityResult

DEFAULT_MAX_RESULT_BYTES = 2_000_000
DEFAULT_MAX_TEST_CASES = 10_000
DEFAULT_MAX_TEST_ID_CHARS = 1024
DEFAULT_MAX_MESSAGE_CHARS = 4096
# A single test case cannot legitimately take longer than this; a larger value
# is hostile or corrupted rather than informative.
MAX_DURATION_SECONDS = 86_400.0


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
        """Aggregate every observed attempt into one bounded suite verdict.

        Any failure or error fails the suite regardless of later retries. A
        suite with no results, or one where every test was skipped, proves
        nothing and is therefore ``NOT_EVALUABLE`` rather than ``PASS``,
        matching ``analysis.history._freshness``.
        """
        failing = {TestCaseResultState.FAIL, TestCaseResultState.ERROR}
        if any(item.state in failing for item in self.tests):
            return QualityResult.FAIL
        if not self.tests:
            return QualityResult.NOT_EVALUABLE
        if all(item.state is TestCaseResultState.SKIPPED for item in self.tests):
            return QualityResult.NOT_EVALUABLE
        return QualityResult.PASS


def _bounded_xml(content: str | bytes, *, max_bytes: int) -> str:
    try:
        raw = content.encode("utf-8") if isinstance(content, str) else content
    except (UnicodeEncodeError, ValueError) as exc:
        raise ResultAdapterError("result document must be UTF-8") from exc
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
    except (ValueError, OverflowError) as exc:
        raise ResultAdapterError(f"invalid test duration {value[:64]!r}") from exc
    if not math.isfinite(duration):
        raise ResultAdapterError("test duration must be finite")
    if duration < 0:
        raise ResultAdapterError("test duration cannot be negative")
    if duration > MAX_DURATION_SECONDS:
        raise ResultAdapterError(f"test duration exceeds {MAX_DURATION_SECONDS} seconds")
    return duration


def _bounded_text(element: ElementTree.Element | None) -> str | None:
    """Return element text bounded before it is materialized into a message.

    ``element.text`` allocates the whole text node; reading only the permitted
    prefix keeps a hostile multi-megabyte reason body out of memory.
    """
    if element is None:
        return None
    text = element.text
    if not text:
        return None
    if len(text) > DEFAULT_MAX_MESSAGE_CHARS:
        text = text[:DEFAULT_MAX_MESSAGE_CHARS]
    return _bounded_message(text)


def _stable_case_id(framework: str, classname: str | None, name: str | None) -> str:
    candidate = "::".join(part for part in (classname, name) if part)
    if not candidate:
        raise ResultAdapterError("test case is missing both classname and name")
    test_id = f"{framework}:{candidate}"
    if len(test_id) > DEFAULT_MAX_TEST_ID_CHARS:
        raise ResultAdapterError(
            f"test case identity exceeds {DEFAULT_MAX_TEST_ID_CHARS} characters"
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in test_id):
        raise ResultAdapterError("test case identity contains control characters")
    return test_id


def _bounded_message(value: str | None) -> str | None:
    """Truncate an over-long result message deterministically so output stays bounded."""
    if value is None:
        return None
    if len(value) > DEFAULT_MAX_MESSAGE_CHARS:
        return value[:DEFAULT_MAX_MESSAGE_CHARS] + "…[truncated]"
    return value


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


class _NoDoctypeBuilder(ElementTree.TreeBuilder):
    """Tree builder that refuses any document type declaration.

    ``XMLParser(forbid_dtd=...)`` only exists on Python 3.13+, so on the
    supported 3.12 baseline the DTD refusal is implemented here instead. Because
    this is a parser-target callback it fires during the parse rather than
    through a substring match, which is what makes entity expansion and
    external-entity payloads fail closed instead of incidentally.
    """

    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        raise ValueError("document type declarations are not permitted")


def _parse_xml(text: str, *, kind: str) -> ElementTree.Element:
    """Parse hostile result XML under an explicit parser policy."""
    try:
        parser = ElementTree.XMLParser(target=_NoDoctypeBuilder())
        parser.feed(text)
        return parser.close()
    except ElementTree.ParseError as exc:
        raise ResultAdapterError(f"malformed {kind} XML") from exc
    except RecursionError as exc:
        raise ResultAdapterError(f"{kind} XML nesting exceeds parser bounds") from exc
    except ValueError as exc:
        # The DTD refusal surfaces here, alongside malformed-input refusals.
        raise ResultAdapterError(f"{kind} XML uses a forbidden XML construct") from exc


def _collect_cases(
    root: ElementTree.Element,
    tag: str,
    *,
    max_cases: int,
) -> list[ElementTree.Element]:
    """Collect test-case elements, refusing to exceed the declared case bound.

    The count is enforced while iterating so an over-large document is rejected
    without first materializing every matching element.
    """
    cases: list[ElementTree.Element] = []
    for case in root.iter(tag):
        cases.append(case)
        if len(cases) > max_cases:
            raise ResultAdapterError(f"result document exceeds {max_cases} test cases")
    return cases


def parse_junit_xml(
    content: str | bytes,
    *,
    framework: str,
    max_bytes: int = DEFAULT_MAX_RESULT_BYTES,
    max_cases: int = DEFAULT_MAX_TEST_CASES,
) -> ParsedTestResults:
    """Parse JUnit XML without resolving external entities or executing repository code."""
    text = _bounded_xml(content, max_bytes=max_bytes)
    root = _parse_xml(text, kind="JUnit")
    cases = _collect_cases(root, "testcase", max_cases=max_cases)

    raw: list[tuple[str, TestCaseResultState, float, str | None]] = []
    for case in cases:
        test_id = _stable_case_id(framework, case.get("classname"), case.get("name"))
        duration = _duration(case.get("time"))
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        if error is not None:
            state = TestCaseResultState.ERROR
            message = _bounded_message(error.get("message"))
        elif failure is not None:
            state = TestCaseResultState.FAIL
            message = _bounded_message(failure.get("message"))
        elif skipped is not None:
            state = TestCaseResultState.SKIPPED
            message = _bounded_message(skipped.get("message"))
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
    root = _parse_xml(text, kind="NUnit")
    cases = _collect_cases(root, "test-case", max_cases=max_cases)

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
        message = _bounded_text(reason)
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
