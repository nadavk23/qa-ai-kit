"""Mobile test runner — gives `test_run` (YAML) and `mobile_batch` the same
step-sequencing semantics the web runner has, but for `ios_*` / `android_*`.

Design notes
------------
* **Import-light.** This module imports neither Appium nor adb at load time.
  Each action handler lazily imports the concrete sync helper for the device's
  platform only when it actually runs. That keeps the runner (and its unit
  tests) usable without the iOS (`appium`) or Android (`adb`) stack installed.
* **Platform routing.** A single mobile step (e.g. `tap`) dispatches to
  `ios_tap_sync` or `android_tap_sync` based on `device.platform`. The YAML/
  batch author writes one platform-neutral step list; the device decides the
  backend.
* **Uniform verdicts.** iOS/Android assert helpers return `(ok, msg)` while
  tap/type raise on failure. The handlers normalise both into the same
  `TestFailure` contract the web runner already uses, so `run_mobile_steps`
  can mirror `run_steps` exactly (PASS / FAIL / ERROR / SKIP + on_failure).

Supported step actions (platform support in brackets):
    tap            [ios, android]  strategy, value, timeout_ms?
    type           [ios, android]  strategy, value, text, clear?, timeout_ms?
    assert_element [ios, android]  strategy, value, present?, timeout_ms?
    assert_text    [ios, android]  text, strategy?, value?, timeout_ms?
    wait           [ios, android]  strategy?, value?, timeout_ms?
    scroll         [ios, android]  direction
    screenshot     [ios, android]  path?
    back           [android]
    home           [android]
    logs           [ios, android]  ios: log_type?, lines?  /  android: filter_expr?, lines?
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from qa_execution.runner_base import TestFailure


# ---------- platform-routing helpers (lazy imports) ----------

def _platform(device: Any) -> str:
    p = getattr(device, "platform", None)
    if p not in ("ios", "android"):
        raise TestFailure(
            f"device has unsupported platform {p!r} (expected 'ios' or 'android')"
        )
    return p


def _default_screenshot_path(platform: str) -> str:
    out_dir = Path.home() / "qa-screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return str(out_dir / f"{platform}-{stamp}.png")


# Each handler returns a one-line success message (str) or raises TestFailure.
# All run the blocking driver call via asyncio.to_thread so the event loop
# stays responsive.

async def _do_tap(device: Any, step: dict[str, Any]) -> str:
    platform = _platform(device)
    strategy = step["strategy"]
    value = step["value"]
    timeout = step.get("timeout_ms", 10000)
    if platform == "ios":
        from qa_execution.mobile import ios_tap_sync
        return await asyncio.to_thread(ios_tap_sync, device, strategy, value, timeout)
    from qa_execution.android import android_tap_sync
    return await asyncio.to_thread(android_tap_sync, device, strategy, value, timeout)


async def _do_type(device: Any, step: dict[str, Any]) -> str:
    platform = _platform(device)
    strategy = step["strategy"]
    value = step["value"]
    text = step["text"]
    clear = step.get("clear", True)
    timeout = step.get("timeout_ms", 10000)
    if platform == "ios":
        from qa_execution.mobile import ios_type_sync
        return await asyncio.to_thread(
            ios_type_sync, device, strategy, value, text, clear, timeout
        )
    from qa_execution.android import android_type_sync
    return await asyncio.to_thread(
        android_type_sync, device, strategy, value, text, clear, timeout
    )


async def _do_assert_element(device: Any, step: dict[str, Any]) -> str:
    platform = _platform(device)
    strategy = step["strategy"]
    value = step["value"]
    present = step.get("present", True)
    timeout = step.get("timeout_ms", 5000)
    if platform == "ios":
        from qa_execution.mobile import ios_assert_element_sync
        ok, msg = await asyncio.to_thread(
            ios_assert_element_sync, device, strategy, value, present, timeout
        )
    else:
        from qa_execution.android import android_assert_element_sync
        ok, msg = await asyncio.to_thread(
            android_assert_element_sync, device, strategy, value, present, timeout
        )
    if not ok:
        raise TestFailure(msg)
    return msg


async def _do_assert_text(device: Any, step: dict[str, Any]) -> str:
    platform = _platform(device)
    text = step["text"]
    strategy = step.get("strategy")
    value = step.get("value")
    timeout = step.get("timeout_ms", 5000)
    if platform == "ios":
        from qa_execution.mobile import ios_assert_text_sync
        ok, msg = await asyncio.to_thread(
            ios_assert_text_sync, device, text, strategy, value, timeout
        )
    else:
        from qa_execution.android import android_assert_text_sync
        ok, msg = await asyncio.to_thread(
            android_assert_text_sync, device, text, strategy, value, timeout
        )
    if not ok:
        raise TestFailure(msg)
    return msg


async def _do_wait(device: Any, step: dict[str, Any]) -> str:
    platform = _platform(device)
    strategy = step.get("strategy")
    value = step.get("value")
    timeout = step.get("timeout_ms", 5000)
    if platform == "ios":
        from qa_execution.mobile import ios_wait_sync
        ok, msg = await asyncio.to_thread(
            ios_wait_sync, device, strategy, value, timeout
        )
    else:
        from qa_execution.android import android_wait_sync
        ok, msg = await asyncio.to_thread(
            android_wait_sync, device, strategy, value, timeout
        )
    if not ok:
        raise TestFailure(msg)
    return msg


async def _do_scroll(device: Any, step: dict[str, Any]) -> str:
    platform = _platform(device)
    direction = step.get("direction", "down")
    if platform == "ios":
        from qa_execution.mobile import ios_scroll_sync
        return await asyncio.to_thread(ios_scroll_sync, device, direction)
    from qa_execution.android import android_scroll_sync
    return await asyncio.to_thread(android_scroll_sync, device, direction)


async def _do_screenshot(device: Any, step: dict[str, Any]) -> str:
    platform = _platform(device)
    path = step.get("path") or _default_screenshot_path(platform)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if platform == "ios":
        from qa_execution.mobile import ios_screenshot_sync
        await asyncio.to_thread(ios_screenshot_sync, device, path)
    else:
        from qa_execution.android import android_screenshot_sync
        await asyncio.to_thread(android_screenshot_sync, device, path)
    return f"screenshot {path}"


async def _do_back(device: Any, step: dict[str, Any]) -> str:
    if _platform(device) != "android":
        raise TestFailure("'back' is only supported on Android")
    from qa_execution.android import android_keyevent_sync
    return await asyncio.to_thread(android_keyevent_sync, device, "back")


async def _do_home(device: Any, step: dict[str, Any]) -> str:
    if _platform(device) != "android":
        raise TestFailure("'home' is only supported on Android")
    from qa_execution.android import android_keyevent_sync
    return await asyncio.to_thread(android_keyevent_sync, device, "home")


async def _do_logs(device: Any, step: dict[str, Any]) -> str:
    platform = _platform(device)
    lines = step.get("lines", 200)
    if platform == "ios":
        from qa_execution.mobile import ios_logs_sync
        log_type = step.get("log_type", "syslog")
        out = await asyncio.to_thread(ios_logs_sync, device, log_type, lines)
    else:
        from qa_execution.android import android_logcat_sync
        filter_expr = step.get("filter_expr")
        out = await asyncio.to_thread(
            android_logcat_sync, device, filter_expr, lines, False
        )
    # logs are diagnostic, not assertions — report a short summary line
    n = len(out.splitlines())
    return f"captured {n} log line(s)"


MOBILE_ACTIONS = {
    "tap": _do_tap,
    "type": _do_type,
    "assert_element": _do_assert_element,
    "assert_text": _do_assert_text,
    "wait": _do_wait,
    "scroll": _do_scroll,
    "screenshot": _do_screenshot,
    "back": _do_back,
    "home": _do_home,
    "logs": _do_logs,
}


async def run_mobile_steps(
    device: Any, steps: list[dict[str, Any]], on_failure: str = "stop"
) -> tuple[list[str], int, int, int]:
    """Run mobile step dicts against an allocated `device`.

    Mirrors `yaml_runner.run_steps` semantics exactly:
    returns (lines, passed, failed, skipped). `on_failure` is 'stop' | 'continue'.
    """
    lines: list[str] = []
    passed = failed = skipped = 0
    for i, step in enumerate(steps, 1):
        action = step.get("action")
        if action not in MOBILE_ACTIONS:
            lines.append(f"[{i}] SKIP — unknown action {action!r}")
            skipped += 1
            continue
        try:
            msg = await MOBILE_ACTIONS[action](device, step)
            lines.append(f"[{i}] PASS {action}: {msg}")
            passed += 1
        except TestFailure as e:
            lines.append(f"[{i}] FAIL {action}: {e}")
            failed += 1
            if on_failure == "stop":
                lines.append("--- Stopped on first failure ---")
                skipped = len(steps) - i
                break
        except Exception as e:
            lines.append(f"[{i}] ERROR {action}: {type(e).__name__}: {e}")
            failed += 1
            if on_failure == "stop":
                lines.append("--- Stopped on first error ---")
                skipped = len(steps) - i
                break
    return lines, passed, failed, skipped
