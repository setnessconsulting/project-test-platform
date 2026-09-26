"""External framework and executor adapter package."""

from test_platform.adapters.results import (
    JEST_ADAPTER,
    PESTER_ADAPTER,
    PLAYWRIGHT_ADAPTER,
    PYTEST_ADAPTER,
    VITEST_ADAPTER,
    AdapterTestResult,
    JUnitFrameworkAdapter,
    ParsedTestResults,
    PesterResultAdapter,
    ResultAdapterError,
    TestCaseResultState,
    parse_junit_xml,
    parse_nunit_xml,
)

__all__ = [
    "JEST_ADAPTER",
    "PESTER_ADAPTER",
    "PLAYWRIGHT_ADAPTER",
    "PYTEST_ADAPTER",
    "VITEST_ADAPTER",
    "AdapterTestResult",
    "JUnitFrameworkAdapter",
    "ParsedTestResults",
    "PesterResultAdapter",
    "ResultAdapterError",
    "TestCaseResultState",
    "parse_junit_xml",
    "parse_nunit_xml",
]
