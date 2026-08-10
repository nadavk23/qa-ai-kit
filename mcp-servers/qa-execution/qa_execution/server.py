"""QA Execution MCP server — Playwright-backed web testing primitives.

Tools are prefixed `web_*` so mobile tools added later can use `ios_*` / `android_*`.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from qa_execution.android import (
    android_assert_element_sync,
    android_assert_text_sync,
    android_inspect_sync,
    android_keyevent_sync,
    android_logcat_sync,
    android_screenshot_sync,
    android_scroll_sync,
    android_tap_sync,
    android_type_sync,
    android_wait_sync,
)
from qa_execution.browser import BrowserSession
from qa_execution import recon
from qa_execution.apk_static import apk_inspect_sync
from qa_execution.mobile_recon import (
    android_a11y_audit_sync,
    android_perf_snapshot_sync,
    ios_a11y_audit_sync,
)
from qa_execution.mobile import (
    DeviceRegistry,
    ios_assert_element_sync,
    ios_assert_text_sync,
    ios_inspect_sync,
    ios_logs_sync,
    ios_screenshot_sync,
    ios_scroll_sync,
    ios_tap_sync,
    ios_type_sync,
    ios_wait_sync,
)
from qa_execution.yaml_runner import run_steps, run_yaml_test

mcp = FastMCP("qa-execution")
session = BrowserSession()
devices = DeviceRegistry()


@mcp.tool()
async def ping() -> str:
    """Return 'pong' to confirm the server is reachable. Use for smoke tests."""
    return "pong"


@mcp.tool()
async def web_navigate(url: str) -> str:
    """Open `url` in the browser. Call before inspect/click/type on a new page.

    URL must include the protocol (http:// or https://).
    """
    await session.ensure_started()
    await session.page.goto(url)
    return f"Navigated. Current URL: {session.page.url}"


@mcp.tool()
async def web_inspect(limit: int = 50) -> str:
    """Snapshot the current page: title, URL, interactive elements with selectors.

    Run this before clicking or typing — it surfaces the selectors you need.
    Returns up to `limit` interactive elements (default 50).
    """
    await session.ensure_started()
    page = session.page
    title = await page.title()
    url = page.url
    elements = await page.evaluate(
        """(limit) => {
            const sel = 'a, button, input, select, textarea, [role="button"], [role="link"]';
            return Array.from(document.querySelectorAll(sel))
                .slice(0, limit)
                .map((el, i) => ({
                    index: i,
                    role: el.tagName.toLowerCase(),
                    id: el.id || '',
                    name: el.getAttribute('name') || '',
                    aria: el.getAttribute('aria-label') || '',
                    text: ((el.innerText || el.value || el.placeholder || '') + '').trim().slice(0, 80),
                }));
        }""",
        limit,
    )
    lines = [f"Title: {title}", f"URL: {url}", f"Interactive elements ({len(elements)}):"]
    for el in elements:
        parts = [f"[{el['index']}] {el['role']}"]
        if el["id"]:
            parts.append(f"#{el['id']}")
        if el["name"]:
            parts.append(f"name={el['name']}")
        if el["aria"]:
            parts.append(f'aria="{el["aria"]}"')
        if el["text"]:
            parts.append(f'text="{el["text"]}"')
        lines.append("  " + " ".join(parts))
    return "\n".join(lines)


@mcp.tool()
async def web_click(selector: str, timeout_ms: int = 10000) -> str:
    """Click an element by CSS selector or Playwright text= selector.

    Examples: `button#submit`, `text=Sign in`, `[aria-label="Close"]`.
    Run web_inspect first to find selectors.
    """
    await session.ensure_started()
    await session.page.click(selector, timeout=timeout_ms)
    return f"Clicked: {selector}"


@mcp.tool()
async def web_type(selector: str, text: str, clear: bool = True) -> str:
    """Type `text` into the input matched by `selector`.

    By default clears the field first. Set clear=False to append.
    """
    await session.ensure_started()
    if clear:
        await session.page.fill(selector, text)
    else:
        await session.page.locator(selector).type(text)
    return f"Typed into {selector}: {text!r}"


@mcp.tool()
async def web_assert_text(
    text: str, selector: str | None = None, timeout_ms: int = 5000
) -> str:
    """Assert `text` appears on the page (optionally scoped to `selector`).

    Returns 'PASS' or 'FAIL: <reason>'. Use as the verification step in a test.
    """
    await session.ensure_started()
    page = session.page
    try:
        if selector:
            await page.locator(selector).filter(has_text=text).first.wait_for(
                timeout=timeout_ms
            )
        else:
            await page.get_by_text(text).first.wait_for(timeout=timeout_ms)
        return f"PASS: text {text!r} found"
    except Exception as e:
        return f"FAIL: text {text!r} not found ({type(e).__name__})"


@mcp.tool()
async def web_assert_element(selector: str, timeout_ms: int = 5000) -> str:
    """Assert an element matching `selector` is visible. Returns PASS/FAIL."""
    await session.ensure_started()
    try:
        await session.page.locator(selector).first.wait_for(
            state="visible", timeout=timeout_ms
        )
        return f"PASS: element {selector} visible"
    except Exception as e:
        return f"FAIL: element {selector} not visible ({type(e).__name__})"


@mcp.tool()
async def web_screenshot(path: str = "") -> str:
    """Capture a full-page screenshot.

    If `path` is empty, saves to ~/qa-screenshots/<timestamp>.png and returns the path.
    """
    await session.ensure_started()
    if not path:
        out_dir = Path.home() / "qa-screenshots"
        out_dir.mkdir(exist_ok=True)
        path = str(out_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.png")
    await session.page.screenshot(path=path, full_page=True)
    return f"Screenshot saved: {path}"


@mcp.tool()
async def web_wait(selector: str | None = None, timeout_ms: int = 5000) -> str:
    """Wait for an element to appear, or sleep for `timeout_ms` if no selector.

    Use sparingly — prefer web_assert_element when you also want to verify.
    """
    await session.ensure_started()
    if selector:
        await session.page.locator(selector).first.wait_for(timeout=timeout_ms)
        return f"Element appeared: {selector}"
    await asyncio.sleep(timeout_ms / 1000)
    return f"Slept {timeout_ms}ms"


@mcp.tool()
async def web_logs(kind: str = "all", clear: bool = False) -> str:
    """Read captured browser logs.

    kind: 'console' (browser console messages), 'network' (HTTP responses), 'all' (default).
    clear: if True, empties the buffer after reading.
    Returns up to the last 100 entries of each kind.
    """
    await session.ensure_started()
    lines: list[str] = []
    if kind in ("console", "all"):
        lines.append("=== CONSOLE ===")
        for entry in session.console_log[-100:]:
            lines.append(f"[{entry['type']}] {entry['text']}")
    if kind in ("network", "all"):
        lines.append("=== NETWORK ===")
        for entry in session.network_log[-100:]:
            lines.append(f"{entry['status']} {entry['method']} {entry['url']}")
    if clear:
        session.console_log.clear()
        session.network_log.clear()
    return "\n".join(lines) if lines else "(no logs)"


@mcp.tool()
async def web_session_save(name: str) -> str:
    """Save the current browser session (cookies, localStorage) to a named file.

    Use after a successful login so future runs can call web_session_load(name)
    and skip the login flow.
    """
    await session.ensure_started()
    sessions_dir = Path.home() / ".qa-execution" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    storage_path = sessions_dir / f"{name}.json"
    await session.context.storage_state(path=str(storage_path))
    return f"Session saved: {storage_path}"


@mcp.tool()
async def web_session_load(name: str) -> str:
    """Load a previously saved browser session.

    Replaces the current browser context — any unsaved state is discarded.
    """
    sessions_dir = Path.home() / ".qa-execution" / "sessions"
    storage_path = sessions_dir / f"{name}.json"
    if not storage_path.exists():
        return f"FAIL: session {name!r} not found at {storage_path}"
    await session.restart_with_storage(str(storage_path))
    return f"Session loaded: {name}"


@mcp.tool()
async def api_request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    expected_status: int | None = None,
) -> str:
    """Send an HTTP request to an API endpoint.

    method: GET, POST, PUT, PATCH, DELETE, etc.
    url: full URL (must include http:// or https://)
    headers: dict of header name → value (optional, e.g. for auth tokens)
    json_body: dict sent as JSON body (optional)
    expected_status: if set, response is graded PASS/FAIL against it (optional)

    Returns status, content-type, and body (truncated to 4KB).
    Use this for API/backend testing when a browser isn't needed.
    """
    method = method.upper()
    async with httpx.AsyncClient(timeout=30.0) as client:
        kwargs: dict[str, Any] = {}
        if headers:
            kwargs["headers"] = headers
        if json_body is not None:
            kwargs["json"] = json_body
        try:
            resp = await client.request(method, url, **kwargs)
        except Exception as e:
            return f"REQUEST ERROR: {type(e).__name__}: {e}"

    body_text = resp.text[:4096]
    if len(resp.text) > 4096:
        body_text += f"\n... (truncated; total {len(resp.text)} bytes)"

    verdict = ""
    if expected_status is not None:
        ok = resp.status_code == expected_status
        verdict = (
            f"\nVERDICT: {'PASS' if ok else 'FAIL'} "
            f"(expected {expected_status}, got {resp.status_code})"
        )

    return (
        f"{method} {url} → {resp.status_code}\n"
        f"Content-Type: {resp.headers.get('content-type', 'n/a')}\n"
        f"Body:\n{body_text}"
        f"{verdict}"
    )


@mcp.tool()
async def web_batch(actions: list[dict[str, Any]], on_failure: str = "stop") -> str:
    """Execute multiple actions in sequence in a single call.

    Each action is a dict shaped like `{"action": "<name>", ...args}`. Available actions:
      - {"action": "navigate", "url": "https://..."}
      - {"action": "click", "selector": "..."}
      - {"action": "type", "selector": "...", "text": "..."}
      - {"action": "assert_text", "text": "...", "selector": "...optional"}
      - {"action": "assert_element", "selector": "..."}
      - {"action": "wait", "selector": "...optional", "timeout_ms": 5000}
      - {"action": "screenshot", "path": "...optional"}
      - {"action": "session_save", "name": "..."}
      - {"action": "session_load", "name": "..."}
      - {"action": "api_request", "method": "GET", "url": "..."}

    on_failure: 'stop' (default) or 'continue'.
    Returns step-by-step results with PASS/FAIL/ERROR per step.
    """
    lines, passed, failed, skipped = await run_steps(session, actions, on_failure)
    verdict = "PASS" if failed == 0 else "FAIL"
    lines.append(
        f"\nBatch verdict: {verdict} ({passed} passed, {failed} failed, {skipped} skipped)"
    )
    return "\n".join(lines)


@mcp.tool()
async def test_run(path: str) -> str:
    """Run a YAML test file. Returns step-by-step results + overall verdict.

    YAML schema:
      name: str              # test name (required)
      description: str       # optional
      on_failure: stop|continue  # default: stop
      steps:
        - action: <one of the actions listed in web_batch>
          ...action args

    See QA AI KIT/mcp-servers/qa-execution/tests/web/example-login.yaml for a sample.

    Note: this runner currently supports web + API actions only. iOS YAML support
    is a roadmap item — for iOS tests in this version, drive the ios_* tools directly.
    """
    return await run_yaml_test(path, session)


# ---------- Auto-discovery recon (Layer 2) ----------

@mcp.tool()
async def web_discover(limit: int = 30) -> str:
    """Map the current page's functionality surface: links, forms, nav, media.

    Recon primitive. Run after web_navigate to see which main flows exist
    (forms are the highest-signal candidates). Returns internal/external links,
    every form with its fields, primary nav labels, and interactive counts.
    """
    await session.ensure_started()
    return await recon.discover(session.page, limit)


@mcp.tool()
async def web_a11y_audit(limit: int = 8) -> str:
    """First-pass structural accessibility scan of the current page.

    Flags the cheap, high-signal WCAG failures: missing image alt, unlabeled
    form fields, buttons/links with no accessible name, missing lang, heading
    order, landmarks, and positive tabindex. Does NOT check color contrast or
    screen-reader flow — returns up to `limit` examples per rule.
    """
    await session.ensure_started()
    return await recon.a11y_audit(session.page, limit)


@mcp.tool()
async def web_perf_snapshot() -> str:
    """Single-load performance snapshot of the current page.

    Reads the browser's own Navigation/Paint/Resource timing: TTFB, First
    Contentful Paint, DOMContentLoaded, load, total transfer weight, request
    count, and DOM size — each with a rough Web-Vitals-style band. First-pass,
    unthrottled; not a lab benchmark.
    """
    await session.ensure_started()
    return await recon.perf_snapshot(session.page)


@mcp.tool()
async def security_headers_check(url: str) -> str:
    """First-pass transport/header security hygiene for a URL.

    Standalone httpx request (no browser needed). Checks HTTPS upgrade, the
    standard security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-
    Options, Referrer-Policy, Permissions-Policy), cookie flags, and version-
    disclosure headers. NOT a penetration test — surface hygiene only.
    """
    return await recon.security_headers(url)


@mcp.tool()
async def web_recon(url: str, link_limit: int = 30, session_name: str = "") -> str:
    """One-shot auto-discovery recon of a web URL across all static dimensions.

    Navigates to `url`, then runs discovery + accessibility + performance +
    security in sequence and returns a single consolidated first-pass report.
    This is the 'point it at a URL and go' entry point.

    session_name: if set, loads that saved browser session (from a prior
        web_session_save) BEFORE navigating — so recon runs against the
        authenticated, logged-in app rather than the public front door. This is
        where real products actually live; recon on an unauthenticated SPA
        landing page usually finds little. Leave empty for public/unauth recon.

    The page is given time to settle after load, so client-rendered (React/Vue/
    Angular) apps are scanned hydrated, not as an empty shell.

    For a deeper pass — walking real flows (login, checkout, search) and
    capturing screenshots — drive the individual tools, or use the
    `auto-discover-recon` skill which orchestrates the login → save → re-scan
    workflow on top of these.
    """
    auth_note = "unauthenticated (public) context"
    if session_name:
        sessions_dir = Path.home() / ".qa-execution" / "sessions"
        storage_path = sessions_dir / f"{session_name}.json"
        if not storage_path.exists():
            return (
                f"FAIL: session {session_name!r} not found at {storage_path}. "
                f"Run a login flow then web_session_save({session_name!r}) first, "
                f"or omit session_name for unauthenticated recon."
            )
        await session.restart_with_storage(str(storage_path))
        auth_note = f"authenticated context (session {session_name!r})"

    await session.ensure_started()
    final_url = await recon.navigate_and_settle(session.page, url)
    sections = [
        f"########## AUTO-DISCOVERY RECON: {url} ##########",
        f"Context: {auth_note}\nLanded on: {final_url}\n",
        await recon.discover(session.page, link_limit),
        await recon.a11y_audit(session.page),
        await recon.perf_snapshot(session.page),
        await recon.security_headers(final_url),
        "########## END RECON — first-pass only; see per-dimension 'go deeper' notes ##########",
    ]
    return "\n\n".join(sections)


@mcp.tool()
async def apk_inspect(apk_path: str) -> str:
    """Static first-pass recon of an APK file — the 'point recon at an APK' entry.

    Reads the APK with `aapt dump badging` WITHOUT installing or running it:
    package identity, version, min/target SDK, launchable entry, all permissions,
    and high-signal security flags (debuggable, dangerous-permission surface).

    Requires the Android SDK build-tools (for aapt/aapt2) — same prerequisite
    family as the android_* tools. For functionality/UI/a11y/perf on the running
    app, install it and use device_allocate + the android_* recon tools.
    """
    return await asyncio.to_thread(apk_inspect_sync, apk_path)


# ---------- Mobile (iOS via Appium) ----------

@mcp.tool()
async def device_allocate(
    platform: str,
    version: str | None = None,
    device_name: str | None = None,
    app: str | None = None,
    bundle_id: str | None = None,
    emulator_name: str | None = None,
    package: str | None = None,
) -> str:
    """Allocate a mobile device session. Returns an opaque token used by ios_*/android_* tools.

    Common:
      platform: "ios" or "android"
      app: absolute path to a .app/.ipa (iOS) or .apk (Android)

    iOS-only:
      version: e.g. "17.5" — defaults to whatever the simulator has
      device_name: e.g. "iPhone 15" (default), "iPhone 15 Pro"
      bundle_id: bundle ID of an installed app (e.g. "com.apple.mobilesafari")
      Provide exactly one of `app` or `bundle_id`.
      Requires Appium 2 + xcuitest driver running externally (default http://127.0.0.1:4723).

    Android-only:
      emulator_name: AVD name to boot if no emulator is already running (e.g. "Pixel_10_Pro_XL")
      package: launch this package after allocation (e.g. "com.android.settings")
      Uses adb directly — no Appium server needed.
    """
    platform_norm = platform.lower()
    if platform_norm == "ios":
        try:
            token, device = await devices.allocate_ios(
                version=version,
                device_name=device_name,
                app=app,
                bundle_id=bundle_id,
            )
        except ValueError as e:
            return f"FAIL: {e}"
        except Exception as e:
            return f"ERROR allocating iOS device: {type(e).__name__}: {e}"
        return (
            f"Allocated iOS device.\n"
            f"  token: {token}\n"
            f"  device_name: {device.device_name}\n"
            f"  version: {device.version or '(simulator default)'}\n"
            f"  app: {device.app or '-'}\n"
            f"  bundle_id: {device.bundle_id or '-'}\n"
            f"Pass this token to every ios_* tool. Call device_release when done."
        )
    if platform_norm == "android":
        try:
            token, device = await devices.allocate_android(
                emulator_name=emulator_name,
                app=app,
                package=package,
            )
        except (ValueError, FileNotFoundError) as e:
            return f"FAIL: {e}"
        except Exception as e:
            return f"ERROR allocating Android device: {type(e).__name__}: {e}"
        return (
            f"Allocated Android device.\n"
            f"  token: {token}\n"
            f"  device_id: {device.device_id}\n"
            f"  package: {device.package or '-'}\n"
            f"Pass this token to every android_* tool. Call device_release when done."
        )
    return f"FAIL: unknown platform {platform!r}. Expected 'ios' or 'android'."


@mcp.tool()
async def device_release(token: str) -> str:
    """Release an allocated device session and shut down its Appium driver."""
    ok = await devices.release(token)
    return f"Released device {token}." if ok else f"FAIL: unknown token {token!r}."


@mcp.tool()
async def device_list() -> str:
    """List active device sessions with their tokens and metadata."""
    items = devices.list()
    if not items:
        return "(no active device sessions)"
    lines = [f"Active devices ({len(items)}):"]
    for d in items:
        lines.append(
            f"  {d['token']} — {d['platform']} {d['device_name']} "
            f"v{d['version'] or 'default'} "
            f"app={d['app'] or '-'} bundle_id={d['bundle_id'] or '-'}"
        )
    return "\n".join(lines)


@mcp.tool()
async def ios_tap(token: str, strategy: str, value: str, timeout_ms: int = 10000) -> str:
    """Tap an element on the allocated iOS device.

    strategy: one of "accessibility_id" (preferred), "predicate", "xpath", "class_chain"
    value: the locator value for that strategy
        - accessibility_id: e.g. "loginButton"
        - predicate:        e.g. "label == 'Sign In'"
        - xpath:            e.g. "//XCUIElementTypeButton[@name='Sign In']"
        - class_chain:      e.g. "**/XCUIElementTypeButton[`label == 'Sign In'`]"
    """
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    try:
        msg = await asyncio.to_thread(ios_tap_sync, device, strategy, value, timeout_ms)
        return f"PASS: {msg}"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


@mcp.tool()
async def ios_type(
    token: str,
    strategy: str,
    value: str,
    text: str,
    clear: bool = True,
    timeout_ms: int = 10000,
) -> str:
    """Type `text` into an iOS input element. Clears the field first by default."""
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    try:
        msg = await asyncio.to_thread(
            ios_type_sync, device, strategy, value, text, clear, timeout_ms
        )
        return f"PASS: {msg}"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


@mcp.tool()
async def ios_assert_element(
    token: str,
    strategy: str,
    value: str,
    present: bool = True,
    timeout_ms: int = 5000,
) -> str:
    """Assert an iOS element is present (or absent, with present=False). Returns PASS/FAIL."""
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    ok, msg = await asyncio.to_thread(
        ios_assert_element_sync, device, strategy, value, present, timeout_ms
    )
    return f"{'PASS' if ok else 'FAIL'}: {msg}"


@mcp.tool()
async def ios_assert_text(
    token: str,
    text: str,
    strategy: str | None = None,
    value: str | None = None,
    timeout_ms: int = 5000,
) -> str:
    """Assert `text` appears on the iOS screen.

    If `strategy` + `value` are provided, only the element's name/label/value is checked.
    Otherwise the whole page source is scanned. Returns PASS/FAIL.
    """
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    ok, msg = await asyncio.to_thread(
        ios_assert_text_sync, device, text, strategy, value, timeout_ms
    )
    return f"{'PASS' if ok else 'FAIL'}: {msg}"


@mcp.tool()
async def ios_inspect(token: str, limit: int = 50) -> str:
    """Snapshot the current iOS screen: list interactive elements with their attributes.

    Run before ios_tap / ios_type to find the right locator values.
    Returns up to `limit` elements (default 50) that expose at least one of
    name / label / value — the attributes you'd locate them by.
    """
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    try:
        return await asyncio.to_thread(ios_inspect_sync, device, limit)
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


@mcp.tool()
async def ios_screenshot(token: str, path: str = "") -> str:
    """Capture a screenshot of the iOS device screen.

    If `path` is empty, saves to ~/qa-screenshots/ios-<timestamp>.png and returns the path.
    """
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    if not path:
        out_dir = Path.home() / "qa-screenshots"
        out_dir.mkdir(exist_ok=True)
        path = str(out_dir / f"ios-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png")
    try:
        await asyncio.to_thread(ios_screenshot_sync, device, path)
        return f"Screenshot saved: {path}"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


@mcp.tool()
async def ios_wait(
    token: str,
    strategy: str | None = None,
    value: str | None = None,
    timeout_ms: int = 5000,
) -> str:
    """Wait for an iOS element to appear, or sleep `timeout_ms` if no locator given."""
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    ok, msg = await asyncio.to_thread(
        ios_wait_sync, device, strategy, value, timeout_ms
    )
    return f"{'PASS' if ok else 'FAIL'}: {msg}"


@mcp.tool()
async def ios_scroll(token: str, direction: str = "down") -> str:
    """Scroll the iOS screen. direction: up / down / left / right."""
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    try:
        msg = await asyncio.to_thread(ios_scroll_sync, device, direction)
        return f"PASS: {msg}"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


@mcp.tool()
async def ios_logs(token: str, log_type: str = "syslog", lines: int = 200) -> str:
    """Read recent iOS device logs — real-time debug primitive for iOS.

    Mirrors `android_logcat`. Snapshot, not streaming — call repeatedly to follow.

    log_type: typically "syslog" (device console) or "crashlog". Available types
              depend on the Appium driver; if your choice isn't supported the
              tool returns the list of valid options.
    lines:    tail at most this many of the most recent entries (default 200).
    """
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    return await asyncio.to_thread(ios_logs_sync, device, log_type, lines)


@mcp.tool()
async def ios_a11y_audit(token: str, limit: int = 12) -> str:
    """First-pass structural accessibility scan of the current iOS screen (recon).

    From the XCUITest hierarchy: interactive elements with no accessibility
    name/label/value, and named elements marked accessible=false. Structural
    only — no contrast, VoiceOver rotor order, or Dynamic Type. Run per screen.
    """
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    try:
        return await asyncio.to_thread(ios_a11y_audit_sync, device, limit)
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


# ---------- Mobile (Android via adb) ----------

@mcp.tool()
async def android_tap(token: str, strategy: str, value: str, timeout_ms: int = 10000) -> str:
    """Tap an element on the allocated Android device.

    strategy: one of "text", "accessibility_id" (content-desc), "resource_id", "xpath"
    value: the locator value
        - text:             e.g. "Sign in"
        - accessibility_id: e.g. "loginButton"
        - resource_id:      e.g. "com.example:id/loginButton"
        - xpath:            e.g. ".//*[@class='android.widget.Button'][@text='Sign in']"

    Finds the element via `uiautomator dump`, computes the center of its bounds,
    and sends `adb shell input tap <x> <y>`.
    """
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    try:
        msg = await asyncio.to_thread(android_tap_sync, device, strategy, value, timeout_ms)
        return f"PASS: {msg}"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


@mcp.tool()
async def android_type(
    token: str,
    strategy: str,
    value: str,
    text: str,
    clear: bool = True,
    timeout_ms: int = 10000,
) -> str:
    """Type `text` into the Android element matched by strategy/value.

    Taps the element first (to focus), then sends `adb shell input text "..."`.
    Spaces are encoded as %s per adb's input convention. By default clears the
    field first via a burst of KEYCODE_DEL (works across Android versions).
    """
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    try:
        msg = await asyncio.to_thread(
            android_type_sync, device, strategy, value, text, clear, timeout_ms
        )
        return f"PASS: {msg}"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


@mcp.tool()
async def android_assert_element(
    token: str,
    strategy: str,
    value: str,
    present: bool = True,
    timeout_ms: int = 5000,
) -> str:
    """Assert an Android element is present (or absent, with present=False). Returns PASS/FAIL."""
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    ok, msg = await asyncio.to_thread(
        android_assert_element_sync, device, strategy, value, present, timeout_ms
    )
    return f"{'PASS' if ok else 'FAIL'}: {msg}"


@mcp.tool()
async def android_assert_text(
    token: str,
    text: str,
    strategy: str | None = None,
    value: str | None = None,
    timeout_ms: int = 5000,
) -> str:
    """Assert `text` appears on the Android screen.

    If `strategy` + `value` are provided, only the matched element's text/desc
    is checked. Otherwise the whole UI dump XML is scanned. Returns PASS/FAIL.
    """
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    ok, msg = await asyncio.to_thread(
        android_assert_text_sync, device, text, strategy, value, timeout_ms
    )
    return f"{'PASS' if ok else 'FAIL'}: {msg}"


@mcp.tool()
async def android_inspect(token: str, limit: int = 50) -> str:
    """Snapshot the current Android screen: list elements with text / desc / resource-id.

    Run before android_tap / android_type to find the right locator values.
    Returns up to `limit` elements that expose at least one of text, content-desc,
    or resource-id — the attributes you'd locate them by.
    """
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    try:
        return await asyncio.to_thread(android_inspect_sync, device, limit)
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


@mcp.tool()
async def android_screenshot(token: str, path: str = "") -> str:
    """Capture a screenshot of the Android device screen.

    If `path` is empty, saves to ~/qa-screenshots/android-<timestamp>.png.
    """
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    if not path:
        out_dir = Path.home() / "qa-screenshots"
        out_dir.mkdir(exist_ok=True)
        path = str(out_dir / f"android-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png")
    try:
        await asyncio.to_thread(android_screenshot_sync, device, path)
        return f"Screenshot saved: {path}"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


@mcp.tool()
async def android_wait(
    token: str,
    strategy: str | None = None,
    value: str | None = None,
    timeout_ms: int = 5000,
) -> str:
    """Wait for an Android element to appear, or sleep `timeout_ms` if no locator given."""
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    ok, msg = await asyncio.to_thread(
        android_wait_sync, device, strategy, value, timeout_ms
    )
    return f"{'PASS' if ok else 'FAIL'}: {msg}"


@mcp.tool()
async def android_scroll(token: str, direction: str = "down") -> str:
    """Scroll the Android screen via a center-to-edge swipe. direction: up/down/left/right."""
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    try:
        msg = await asyncio.to_thread(android_scroll_sync, device, direction)
        return f"PASS: {msg}"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


@mcp.tool()
async def android_back(token: str) -> str:
    """Press the Android back button (KEYCODE_BACK)."""
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    try:
        msg = await asyncio.to_thread(android_keyevent_sync, device, "back")
        return f"PASS: {msg}"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


@mcp.tool()
async def android_home(token: str) -> str:
    """Press the Android home button (KEYCODE_HOME)."""
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    try:
        msg = await asyncio.to_thread(android_keyevent_sync, device, "home")
        return f"PASS: {msg}"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


@mcp.tool()
async def android_logcat(
    token: str,
    filter_expr: str | None = None,
    lines: int = 200,
    clear: bool = False,
) -> str:
    """Tail recent Android logcat output — primary real-time debug primitive for Android.

    filter_expr: standard logcat tag-priority spec, e.g. "MyApp:V *:S" to show
                 verbose-from-MyApp and silence everything else. Omit to show all.
    lines: how many recent lines to return (default 200, max useful ~1000).
    clear: if True, clears the logcat buffer instead of reading (returns confirmation).

    Internally runs `adb -s <id> logcat -d -t <lines> [filter]`. Non-streaming —
    each call is a snapshot, not a live tail. Call repeatedly to follow.
    """
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    try:
        return await asyncio.to_thread(
            android_logcat_sync, device, filter_expr, lines, clear
        )
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


@mcp.tool()
async def android_a11y_audit(token: str, limit: int = 12) -> str:
    """First-pass structural accessibility scan of the current Android screen (recon).

    From the uiautomator hierarchy: clickable elements with no text/content-desc
    (invisible to TalkBack), images with no content-desc, and touch targets below
    48dp. Structural only — no contrast, TalkBack focus order, or dynamic type.
    Run per screen.
    """
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    try:
        return await asyncio.to_thread(android_a11y_audit_sync, device, limit)
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


@mcp.tool()
async def android_perf_snapshot(token: str, package: str = "") -> str:
    """First-pass Android performance snapshot for the app (recon).

    Cold-start time (`am start -W`), memory (TOTAL PSS via `dumpsys meminfo`),
    and frame jank (`dumpsys gfxinfo`), each with a rough band. Single sample on
    an emulator/device — not a controlled benchmark. Uses the session's package
    unless `package` is given. Interact with the app before running so gfxinfo
    has frames to report.
    """
    try:
        device = devices.get(token)
    except KeyError as e:
        return f"FAIL: {e}"
    try:
        return await asyncio.to_thread(android_perf_snapshot_sync, device, package)
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
