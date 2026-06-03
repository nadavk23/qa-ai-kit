"""QA Execution MCP server — Playwright-backed web testing primitives.

Tools are prefixed `web_*` so mobile tools added later can use `ios_*` / `android_*`.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from qa_execution.browser import BrowserSession
from qa_execution.yaml_runner import run_steps, run_yaml_test

mcp = FastMCP("qa-execution")
session = BrowserSession()


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
    """
    return await run_yaml_test(path, session)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
