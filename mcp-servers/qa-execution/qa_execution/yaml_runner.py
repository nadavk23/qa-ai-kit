"""YAML test runner — used by both `test_run` and `web_batch` MCP tools."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from qa_execution.browser import BrowserSession
from qa_execution.runner_base import TestFailure  # re-exported for callers

__all__ = ["TestFailure", "run_steps", "run_yaml_test", "ACTIONS"]


async def _do_navigate(session: BrowserSession, step: dict[str, Any]) -> str:
    url = step["url"]
    await session.ensure_started()
    await session.page.goto(url)
    return f"navigated to {url}"


async def _do_click(session: BrowserSession, step: dict[str, Any]) -> str:
    await session.ensure_started()
    sel = step["selector"]
    await session.page.click(sel, timeout=step.get("timeout_ms", 10000))
    return f"clicked {sel}"


async def _do_type(session: BrowserSession, step: dict[str, Any]) -> str:
    await session.ensure_started()
    sel = step["selector"]
    text = step["text"]
    if step.get("clear", True):
        await session.page.fill(sel, text)
    else:
        await session.page.locator(sel).type(text)
    return f"typed into {sel}"


async def _do_assert_text(session: BrowserSession, step: dict[str, Any]) -> str:
    await session.ensure_started()
    text = step["text"]
    sel = step.get("selector")
    timeout = step.get("timeout_ms", 5000)
    try:
        if sel:
            await session.page.locator(sel).filter(has_text=text).first.wait_for(
                timeout=timeout
            )
        else:
            await session.page.get_by_text(text).first.wait_for(timeout=timeout)
        return f"text {text!r} present"
    except Exception as e:
        raise TestFailure(f"text {text!r} not found ({type(e).__name__})")


async def _do_assert_element(session: BrowserSession, step: dict[str, Any]) -> str:
    await session.ensure_started()
    sel = step["selector"]
    timeout = step.get("timeout_ms", 5000)
    try:
        await session.page.locator(sel).first.wait_for(state="visible", timeout=timeout)
        return f"element {sel} visible"
    except Exception as e:
        raise TestFailure(f"element {sel} not visible ({type(e).__name__})")


async def _do_wait(session: BrowserSession, step: dict[str, Any]) -> str:
    sel = step.get("selector")
    timeout = step.get("timeout_ms", 5000)
    if sel:
        await session.ensure_started()
        await session.page.locator(sel).first.wait_for(timeout=timeout)
        return f"waited for {sel}"
    await asyncio.sleep(timeout / 1000)
    return f"slept {timeout}ms"


async def _do_screenshot(session: BrowserSession, step: dict[str, Any]) -> str:
    await session.ensure_started()
    path = step.get("path") or str(
        Path.home() / "qa-screenshots" / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
    )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    await session.page.screenshot(path=path, full_page=True)
    return f"screenshot {path}"


async def _do_session_save(session: BrowserSession, step: dict[str, Any]) -> str:
    await session.ensure_started()
    name = step["name"]
    sessions_dir = Path.home() / ".qa-execution" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    storage_path = sessions_dir / f"{name}.json"
    await session.context.storage_state(path=str(storage_path))
    return f"session saved: {name}"


async def _do_session_load(session: BrowserSession, step: dict[str, Any]) -> str:
    name = step["name"]
    sessions_dir = Path.home() / ".qa-execution" / "sessions"
    storage_path = sessions_dir / f"{name}.json"
    if not storage_path.exists():
        raise TestFailure(f"session {name!r} not found")
    await session.restart_with_storage(str(storage_path))
    return f"session loaded: {name}"


async def _do_api_request(session: BrowserSession, step: dict[str, Any]) -> str:
    method = step["method"].upper()
    url = step["url"]
    headers = step.get("headers", {})
    json_body = step.get("json_body")
    expected = step.get("expected_status")

    async with httpx.AsyncClient(timeout=30.0) as client:
        kwargs: dict[str, Any] = {"headers": headers}
        if json_body is not None:
            kwargs["json"] = json_body
        resp = await client.request(method, url, **kwargs)

    if expected is not None and resp.status_code != expected:
        raise TestFailure(
            f"API {method} {url}: expected status {expected}, got {resp.status_code}"
        )
    return f"API {method} {url} → {resp.status_code}"


ACTIONS = {
    "navigate": _do_navigate,
    "click": _do_click,
    "type": _do_type,
    "assert_text": _do_assert_text,
    "assert_element": _do_assert_element,
    "wait": _do_wait,
    "screenshot": _do_screenshot,
    "session_save": _do_session_save,
    "session_load": _do_session_load,
    "api_request": _do_api_request,
}


async def run_steps(
    session: BrowserSession, steps: list[dict[str, Any]], on_failure: str = "stop"
) -> tuple[list[str], int, int, int]:
    """Run a list of step dicts. Returns (lines, passed, failed, skipped)."""
    lines: list[str] = []
    passed = failed = skipped = 0
    for i, step in enumerate(steps, 1):
        action = step.get("action")
        if action not in ACTIONS:
            lines.append(f"[{i}] SKIP — unknown action {action!r}")
            skipped += 1
            continue
        try:
            msg = await ACTIONS[action](session, step)
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


async def run_yaml_test(path: str, session: BrowserSession, devices: Any = None) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"FAIL: test file not found: {path}"

    spec = yaml.safe_load(p.read_text())
    name = spec.get("name", p.stem)
    on_failure = spec.get("on_failure", "stop")
    steps = spec.get("steps", [])
    platform = str(spec.get("platform", "web")).lower()

    if platform in ("ios", "android"):
        return await _run_mobile_yaml(p, name, platform, spec, steps, on_failure, devices)

    lines = [f"=== Test: {name} (web) ===", f"File: {p}"]
    step_lines, passed, failed, skipped = await run_steps(session, steps, on_failure)
    lines.extend(step_lines)
    verdict = "PASS" if failed == 0 else "FAIL"
    lines.append(f"\nVerdict: {verdict} ({passed} passed, {failed} failed, {skipped} skipped)")
    return "\n".join(lines)


async def _run_mobile_yaml(
    p: Path,
    name: str,
    platform: str,
    spec: dict[str, Any],
    steps: list[dict[str, Any]],
    on_failure: str,
    devices: Any,
) -> str:
    """Run a mobile (`platform: ios|android`) YAML test.

    Allocates a fresh device session from the spec's `target:` block, runs the
    steps via the mobile runner, then always releases the session. `devices`
    must be the server's DeviceRegistry.
    """
    from qa_execution.mobile_runner import run_mobile_steps

    if devices is None:
        return (
            f"FAIL: test {name!r} declares platform={platform!r} but no device "
            f"registry was provided to the runner."
        )
    target = spec.get("target", {}) or {}

    lines = [f"=== Test: {name} ({platform}) ===", f"File: {p}"]
    token = None
    try:
        if platform == "ios":
            token, _device = await devices.allocate_ios(
                version=target.get("version"),
                device_name=target.get("device_name"),
                app=target.get("app"),
                bundle_id=target.get("bundle_id"),
            )
        else:  # android
            token, _device = await devices.allocate_android(
                emulator_name=target.get("emulator_name"),
                app=target.get("app"),
                package=target.get("package"),
            )
    except Exception as e:
        lines.append(f"SETUP ERROR: could not allocate {platform} device: "
                     f"{type(e).__name__}: {e}")
        lines.append("\nVerdict: FAIL (device allocation failed)")
        return "\n".join(lines)

    try:
        device = devices.get(token)
        step_lines, passed, failed, skipped = await run_mobile_steps(
            device, steps, on_failure
        )
        lines.extend(step_lines)
        verdict = "PASS" if failed == 0 else "FAIL"
        lines.append(
            f"\nVerdict: {verdict} ({passed} passed, {failed} failed, {skipped} skipped)"
        )
        return "\n".join(lines)
    finally:
        if token is not None:
            await devices.release(token)
