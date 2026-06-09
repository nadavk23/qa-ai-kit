"""Lightweight shared primitives for the test runners.

Kept dependency-free (stdlib only) so both the web runner (`yaml_runner`,
which pulls in Playwright/httpx) and the mobile runner (`mobile_runner`, which
must stay importable without Appium/adb) can share the same `TestFailure`
contract without dragging in heavy optional dependencies.
"""

from __future__ import annotations


class TestFailure(Exception):
    """Raised by an action when its assertion fails.

    Distinct from unexpected errors: a `TestFailure` is a clean assertion miss
    (reported as FAIL), whereas any other exception is reported as ERROR.
    """

    __test__ = False  # tell pytest this is not a test class despite the name
