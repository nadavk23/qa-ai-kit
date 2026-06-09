"""Unit tests for the mobile test runner.

These exercise `run_mobile_steps` without any real device, Appium, or adb:
* the Android path monkeypatches the (stdlib-only) `qa_execution.android` sync
  helpers,
* the iOS path injects a fake `qa_execution.mobile` module so we never import
  Appium.

What we're verifying is the *runner contract* — dispatch, platform routing,
verdict mapping (PASS/FAIL/ERROR/SKIP), and `on_failure` semantics — not the
drivers themselves (those need a device and are covered by live smoke tests).
"""

from __future__ import annotations

import sys
import types

import pytest

from qa_execution import mobile_runner
from qa_execution.runner_base import TestFailure


class FakeDevice:
    def __init__(self, platform: str = "android") -> None:
        self.platform = platform


# ---------- Android driver fakes ----------

@pytest.fixture
def android_calls(monkeypatch):
    """Patch every android sync helper to record calls and return canned values.

    Returns a list of (fn_name, args) tuples so tests can assert routing/args.
    Assertion-style helpers return (True, msg) by default; individual tests
    override specific ones to simulate failures.
    """
    import qa_execution.android as a

    calls: list[tuple] = []

    def rec(name, ret):
        def _fn(*args):
            calls.append((name, args))
            return ret
        return _fn

    monkeypatch.setattr(a, "android_tap_sync", rec("tap", "tapped"))
    monkeypatch.setattr(a, "android_type_sync", rec("type", "typed"))
    monkeypatch.setattr(a, "android_scroll_sync", rec("scroll", "scrolled down"))
    monkeypatch.setattr(a, "android_screenshot_sync", rec("screenshot", "/tmp/x.png"))
    monkeypatch.setattr(a, "android_keyevent_sync", rec("keyevent", "sent key"))
    monkeypatch.setattr(a, "android_logcat_sync", rec("logcat", "line1\nline2\nline3"))
    monkeypatch.setattr(
        a, "android_assert_element_sync", rec("assert_element", (True, "is present"))
    )
    monkeypatch.setattr(
        a, "android_assert_text_sync", rec("assert_text", (True, "found"))
    )
    monkeypatch.setattr(a, "android_wait_sync", rec("wait", (True, "appeared")))
    return calls


async def test_all_actions_pass_android(android_calls):
    device = FakeDevice("android")
    steps = [
        {"action": "tap", "strategy": "text", "value": "OK"},
        {"action": "type", "strategy": "resource_id", "value": "f", "text": "hi"},
        {"action": "assert_element", "strategy": "text", "value": "OK"},
        {"action": "assert_text", "text": "Welcome"},
        {"action": "wait", "strategy": "text", "value": "OK"},
        {"action": "scroll", "direction": "down"},
        {"action": "screenshot", "path": "/tmp/qa-test-shot.png"},
        {"action": "back"},
        {"action": "home"},
        {"action": "logs", "lines": 10},
    ]
    lines, passed, failed, skipped = await mobile_runner.run_mobile_steps(device, steps)
    assert (passed, failed, skipped) == (10, 0, 0), "\n".join(lines)
    assert all("PASS" in ln for ln in lines)
    # logs action summarises the captured line count
    assert "captured 3 log line(s)" in lines[-1]


async def test_assert_failure_stops(android_calls, monkeypatch):
    import qa_execution.android as a
    monkeypatch.setattr(
        a, "android_assert_text_sync",
        lambda *args: (False, "text 'nope' not found"),
    )
    device = FakeDevice("android")
    steps = [
        {"action": "tap", "strategy": "text", "value": "OK"},
        {"action": "assert_text", "text": "nope"},
        {"action": "tap", "strategy": "text", "value": "never"},  # should be skipped
    ]
    lines, passed, failed, skipped = await mobile_runner.run_mobile_steps(
        device, steps, on_failure="stop"
    )
    assert passed == 1
    assert failed == 1
    assert skipped == 1
    assert any("FAIL assert_text" in ln for ln in lines)
    assert any("Stopped on first failure" in ln for ln in lines)


async def test_assert_failure_continue(android_calls, monkeypatch):
    import qa_execution.android as a
    monkeypatch.setattr(
        a, "android_assert_element_sync",
        lambda *args: (False, "missing"),
    )
    device = FakeDevice("android")
    steps = [
        {"action": "assert_element", "strategy": "text", "value": "A"},
        {"action": "tap", "strategy": "text", "value": "B"},
    ]
    lines, passed, failed, skipped = await mobile_runner.run_mobile_steps(
        device, steps, on_failure="continue"
    )
    assert passed == 1
    assert failed == 1
    assert skipped == 0


async def test_unknown_action_skipped(android_calls):
    device = FakeDevice("android")
    steps = [{"action": "teleport", "to": "moon"}]
    lines, passed, failed, skipped = await mobile_runner.run_mobile_steps(device, steps)
    assert (passed, failed, skipped) == (0, 0, 1)
    assert "SKIP" in lines[0] and "teleport" in lines[0]


async def test_driver_exception_is_error(android_calls, monkeypatch):
    import qa_execution.android as a

    def boom(*args):
        raise RuntimeError("adb exploded")

    monkeypatch.setattr(a, "android_tap_sync", boom)
    device = FakeDevice("android")
    steps = [{"action": "tap", "strategy": "text", "value": "X"}]
    lines, passed, failed, skipped = await mobile_runner.run_mobile_steps(device, steps)
    assert failed == 1 and passed == 0
    assert "ERROR tap" in lines[0] and "RuntimeError" in lines[0]


async def test_back_home_rejected_on_ios():
    device = FakeDevice("ios")
    for action in ("back", "home"):
        lines, passed, failed, skipped = await mobile_runner.run_mobile_steps(
            device, [{"action": action}]
        )
        assert failed == 1, action
        assert "only supported on Android" in lines[0]


async def test_unsupported_platform_is_failure():
    device = FakeDevice("windows-phone")
    lines, passed, failed, skipped = await mobile_runner.run_mobile_steps(
        device, [{"action": "tap", "strategy": "text", "value": "X"}]
    )
    assert failed == 1
    assert "unsupported platform" in lines[0]


# ---------- iOS routing via injected fake module ----------

@pytest.fixture
def fake_ios_module(monkeypatch):
    """Inject a fake `qa_execution.mobile` so the iOS branch routes without Appium."""
    calls: list[tuple] = []
    mod = types.ModuleType("qa_execution.mobile")

    def rec(name, ret):
        def _fn(*args):
            calls.append((name, args))
            return ret
        return _fn

    mod.ios_tap_sync = rec("ios_tap", "tapped")
    mod.ios_type_sync = rec("ios_type", "typed")
    mod.ios_assert_element_sync = rec("ios_assert_element", (True, "present"))
    mod.ios_assert_text_sync = rec("ios_assert_text", (True, "found"))
    mod.ios_wait_sync = rec("ios_wait", (True, "appeared"))
    mod.ios_scroll_sync = rec("ios_scroll", "scrolled")
    mod.ios_screenshot_sync = rec("ios_screenshot", "/tmp/i.png")
    mod.ios_logs_sync = rec("ios_logs", "a\nb")
    monkeypatch.setitem(sys.modules, "qa_execution.mobile", mod)
    return calls


async def test_ios_routing(fake_ios_module):
    device = FakeDevice("ios")
    steps = [
        {"action": "tap", "strategy": "accessibility_id", "value": "General"},
        {"action": "assert_text", "text": "Settings"},
        {"action": "screenshot", "path": "/tmp/qa-ios-shot.png"},
    ]
    lines, passed, failed, skipped = await mobile_runner.run_mobile_steps(device, steps)
    assert (passed, failed, skipped) == (3, 0, 0), "\n".join(lines)
    called = [c[0] for c in fake_ios_module]
    assert called == ["ios_tap", "ios_assert_text", "ios_screenshot"]
