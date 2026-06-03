# qa-execution

MCP server providing web + API + iOS execution primitives for QA work, built on Playwright + httpx + Appium.

## Tools (26)

### Web + API (15)

| Tool | Purpose |
|---|---|
| `ping` | Confirm the server is alive |
| `web_navigate(url)` | Open a URL |
| `web_inspect(limit=50)` | Snapshot title + URL + interactive elements with selectors |
| `web_click(selector, timeout_ms=10000)` | Click an element |
| `web_type(selector, text, clear=True)` | Type into an input |
| `web_assert_text(text, selector?, timeout_ms=5000)` | Verify text appears |
| `web_assert_element(selector, timeout_ms=5000)` | Verify an element is visible |
| `web_screenshot(path?)` | Full-page screenshot |
| `web_wait(selector?, timeout_ms=5000)` | Wait for element or sleep |
| `web_logs(kind="all", clear=False)` | Read captured console + network logs |
| `web_session_save(name)` | Persist cookies/localStorage after login |
| `web_session_load(name)` | Reuse a saved session — skips re-login |
| `web_batch(actions, on_failure="stop")` | Run multiple actions in one call |
| `api_request(method, url, ...)` | HTTP request for API testing |
| `test_run(path)` | Run a YAML test file (web + API only — iOS YAML support is roadmap) |

### iOS (Appium) (11)

| Tool | Purpose |
|---|---|
| `device_allocate(platform, version?, device_name?, app?, bundle_id?)` | Start an Appium session against an iOS Simulator; returns a token |
| `device_release(token)` | Close the Appium session for `token` |
| `device_list()` | List active device sessions |
| `ios_tap(token, strategy, value, timeout_ms=10000)` | Tap an element |
| `ios_type(token, strategy, value, text, clear=True, timeout_ms=10000)` | Type into an input |
| `ios_assert_element(token, strategy, value, present=True, timeout_ms=5000)` | Assert presence/absence |
| `ios_assert_text(token, text, strategy?, value?, timeout_ms=5000)` | Assert text appears |
| `ios_inspect(token, limit=50)` | List elements with name / label / value |
| `ios_screenshot(token, path?)` | Screenshot the device screen |
| `ios_wait(token, strategy?, value?, timeout_ms=5000)` | Wait for an element or sleep |
| `ios_scroll(token, direction="down")` | Scroll up / down / left / right |

iOS locator strategies: `accessibility_id` (preferred), `predicate`, `xpath`, `class_chain`.

## What the agent can do (prompt → tools)

| What you want to do | What the agent will use |
|---|---|
| See what's on screen | `web_navigate` → `web_screenshot` → describe |
| Test a flow end-to-end | `web_batch` or `test_run` |
| Check for visual bugs | `web_navigate` → `web_screenshot` → describe deviations |
| Test after login | `web_session_load` (if saved) → `web_navigate` → `web_assert_*` |
| Write a YAML test | Agent writes the file with the schema below |
| Run a test | `test_run("path/to/test.yaml")` |
| Debug a broken feature | `web_navigate` → `web_inspect` → `web_logs` → `web_screenshot` |
| Check API response | `api_request(method, url, expected_status=200)` |
| Check logs | `web_navigate` → action → `web_logs(kind="network")` |
| Test an iOS app | `device_allocate(platform="ios", bundle_id="...")` → `ios_inspect` → `ios_tap` / `ios_type` / `ios_assert_*` → `device_release` |
| Test an Android app | **Roadmap (v0.3)** — Appium UIAutomator2 driver, `android_*` tools |

## YAML test schema

```yaml
name: Login flow regression          # required
description: Optional description
on_failure: stop                     # stop (default) | continue
steps:
  - action: navigate
    url: https://app.example.com/login
  - action: type
    selector: 'input[name="email"]'
    text: user@test.com
  - action: type
    selector: 'input[name="password"]'
    text: hunter2
  - action: click
    selector: 'button[type="submit"]'
  - action: assert_text
    text: Welcome back
    timeout_ms: 10000
  - action: screenshot
    path: artifacts/login-success.png
```

### Supported actions in `web_batch` and `test_run`

- `navigate` — `url`
- `click` — `selector`, `timeout_ms?`
- `type` — `selector`, `text`, `clear?`
- `assert_text` — `text`, `selector?`, `timeout_ms?`
- `assert_element` — `selector`, `timeout_ms?`
- `wait` — `selector?`, `timeout_ms?`
- `screenshot` — `path?`
- `session_save` — `name`
- `session_load` — `name`
- `api_request` — `method`, `url`, `headers?`, `json_body?`, `expected_status?`

See `tests/web/example-login.yaml` for a working sample.

## Install

Requires Python 3.10+.

### Option A — dedicated venv (recommended for first-time setup)

```bash
cd "$HOME/Projects/QA AI KIT/mcp-servers/qa-execution"
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
```

Register with Claude using the venv's Python explicitly:

```bash
claude mcp add qa-execution -- "$HOME/Projects/QA AI KIT/mcp-servers/qa-execution/.venv/bin/python" -m qa_execution
```

### Option B — uv (faster, isolated, no venv to activate)

```bash
cd "$HOME/Projects/QA AI KIT/mcp-servers/qa-execution"
uv tool install .
uv tool run playwright install chromium
claude mcp add qa-execution -- qa-execution
```

### Verify

```bash
claude mcp list
```

You should see `qa-execution`. Restart your Claude Code session and the tools become available.

### iOS prerequisites (only if you'll use the `ios_*` tools)

1. **Xcode + Command Line Tools** — install from the App Store, then `xcode-select --install`.
2. **Node.js** — needed to run the Appium server.
3. **Appium 2 + xcuitest driver:**

   ```bash
   npm install -g appium
   appium driver install xcuitest
   ```

4. **Run the Appium server before invoking the MCP tools:**

   ```bash
   appium  # listens on http://127.0.0.1:4723 by default
   ```

   Override the URL via the `QA_APPIUM_URL` environment variable if needed.

5. **An iOS Simulator** — created automatically by `device_allocate` if you pass `device_name` + `version` matching an available runtime. Inspect available runtimes with `xcrun simctl list`.

## Smoke tests

In a Claude Code session, try each capability:

```
Use qa-execution: ping.
```

```
Use qa-execution to navigate to https://example.com, inspect it, and tell me the title.
```

```
Use qa-execution.api_request to GET https://httpbin.org/status/200 and verify status 200.
```

```
Use qa-execution.test_run to execute mcp-servers/qa-execution/tests/web/example-login.yaml.
```

```
Use qa-execution: device_allocate platform=ios bundle_id=com.apple.mobilesafari,
then ios_inspect, then ios_screenshot, then device_release.
```

## Where state lives

- **Screenshots** — `~/qa-screenshots/<timestamp>.png` by default
- **Saved sessions** — `~/.qa-execution/sessions/<name>.json` (contains auth cookies — keep private)
- **Test artifacts** — wherever your YAML test specifies via `screenshot.path`

## Roadmap

- **v0.1**: web + API, headless Chromium, single page session, YAML test runner
- **v0.2** (current): iOS Simulator via Appium (`device_*` + `ios_*` tools)
- **v0.3**: Android via Appium UIAutomator2 (`android_*` tools), iOS YAML test runner support
- **v0.4**: CLI testing (`cli_*` tools), Chrome extension testing, real-device farm integration
- Later: multiple tabs, headful toggle, request mocking/interception, video recording, parameterized tests

## Limitations (v0.2)

- Single browser context per server process. Closing the server discards in-memory state — use `web_session_save` first if you need it back.
- Network logs capture response metadata (status, method, URL) — not bodies.
- No request mocking yet.
- Browser is headless only — you'll see what's happening via screenshots and logs.
- `api_request` supports JSON bodies only. Raw text/binary support is roadmap.
- **iOS**: Simulator only (no real devices yet). Appium server runs externally — the MCP does not start/stop it. YAML test runner doesn't yet support `ios_*` actions; use the MCP tools directly.
- No Android yet — v0.3.

## Troubleshooting

**`playwright install chromium` fails**: ensure you're in the same environment where you installed the package. With venv: `source .venv/bin/activate` first. With uv tool: use `uv tool run playwright install chromium`.

**Tools don't appear in Claude**: check `claude mcp list`. If `qa-execution` is missing, re-run `claude mcp add`. If listed but tools don't show, restart your Claude Code session.

**Browser fails to launch**: on Linux you may need `playwright install-deps`. On macOS this is usually fine.

**`api_request` times out**: the default timeout is 30s. For long-running endpoints, file an issue or fork to extend.
