# qa-execution

MCP server providing web + API + iOS + Android execution primitives for QA work, built on Playwright + httpx + Appium (iOS) + direct `adb` (Android).

## Tools (50)

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

### Auto-discovery recon (8)

First-pass, breadth-over-depth mapping of a live target. Deliberately shallow — enough signal to prove value and point where to go deeper, **not** a full audit. See the `auto-discover-recon` skill, which orchestrates these plus flow-walking. Web + APK/IPA-static tools live here; runtime mobile a11y/perf tools live in the iOS/Android sections.

| Tool | Purpose |
|---|---|
| `web_recon(url, link_limit=30, session_name="")` | One-shot: navigate (with SPA settle) + discovery + accessibility + performance + security in one report. `session_name` loads a saved auth session first, so recon maps the **logged-in** app. The "point it at a URL and go" entry point. |
| `web_discover(limit=30)` | Map the current page's functionality surface: internal/external links, forms + their fields, primary nav, interactive/media counts |
| `web_a11y_audit(limit=8)` | First-pass structural accessibility scan: missing alt, unlabeled fields, nameless controls, `lang`, heading order, landmarks, positive tabindex. **No color-contrast / screen-reader check.** |
| `web_perf_snapshot()` | Single-load timing from the browser: TTFB, FCP, DOMContentLoaded, load, transfer weight, request count, DOM size, each with a rough Web-Vitals band. Unthrottled — not a lab benchmark. |
| `security_headers_check(url)` | Standalone httpx check of HTTPS upgrade, security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy), cookie flags, version disclosure. **Surface hygiene only — not a pentest.** |
| `apk_inspect(apk_path)` | Static APK recon via `aapt dump badging` — **no device needed**. Package identity, version, min/target SDK, launchable entry, all permissions, and security flags (debuggable, dangerous-permission surface). The "point recon at an APK" entry point. |
| `apk_security(apk_path)` | Deeper static APK security via `aapt dump xmltree` — **no device**. Per-component exported flags + permission protection, allowBackup, cleartext traffic, network-security-config. |
| `ipa_inspect(ipa_path)` | Static IPA recon via Info.plist (zip + plistlib) — **no device, no Xcode**. Bundle identity, min iOS, privacy-usage strings, App Transport Security posture, URL schemes, background modes. |

### Cross-platform device session (3)

| Tool | Purpose |
|---|---|
| `device_allocate(platform, ...)` | Start a session against iOS Simulator or Android emulator; returns a token. iOS args: `version`, `device_name`, `app`, `bundle_id`. Android args: `emulator_name`, `app`, `package`. |
| `device_release(token)` | Close the session for `token` (iOS: quits Appium driver; Android: relinquishes the handle, emulator keeps running) |
| `device_list()` | List active device sessions across platforms |

### iOS (Appium) (11)

| Tool | Purpose |
|---|---|
| `ios_tap(token, strategy, value, timeout_ms=10000)` | Tap an element |
| `ios_type(token, strategy, value, text, clear=True, timeout_ms=10000)` | Type into an input |
| `ios_assert_element(token, strategy, value, present=True, timeout_ms=5000)` | Assert presence/absence |
| `ios_assert_text(token, text, strategy?, value?, timeout_ms=5000)` | Assert text appears |
| `ios_inspect(token, limit=50)` | List elements with name / label / value |
| `ios_screenshot(token, path?)` | Screenshot the device screen |
| `ios_wait(token, strategy?, value?, timeout_ms=5000)` | Wait for an element or sleep |
| `ios_scroll(token, direction="down")` | Scroll up / down / left / right |
| `ios_logs(token, log_type="syslog", lines=200)` | Tail recent device logs (real-time debug) |
| `ios_a11y_audit(token, limit=12)` | **Recon.** Structural a11y: interactive elements with no accessibility name/label, `accessible=false` elements. No contrast / VoiceOver order. |
| `ios_perf_snapshot(token)` | **Recon.** Cold-launch time via terminate + timed `activateApp`. Single wall-clock sample; memory/frame timing still need Instruments. |

iOS locator strategies: `accessibility_id` (preferred), `predicate`, `xpath`, `class_chain`.

### Android (adb) (13)

| Tool | Purpose |
|---|---|
| `android_tap(token, strategy, value, timeout_ms=10000)` | Tap an element (finds via uiautomator dump, taps center of bounds) |
| `android_type(token, strategy, value, text, clear=True, timeout_ms=10000)` | Type into an input |
| `android_assert_element(token, strategy, value, present=True, timeout_ms=5000)` | Assert presence/absence |
| `android_assert_text(token, text, strategy?, value?, timeout_ms=5000)` | Assert text appears |
| `android_inspect(token, limit=50)` | List elements with text / desc / resource-id |
| `android_screenshot(token, path?)` | Screenshot via `adb exec-out screencap -p` |
| `android_wait(token, strategy?, value?, timeout_ms=5000)` | Wait for an element or sleep |
| `android_scroll(token, direction="down")` | Center-to-edge swipe; up/down/left/right |
| `android_back(token)` | KEYCODE_BACK |
| `android_home(token)` | KEYCODE_HOME |
| `android_logcat(token, filter_expr?, lines=200, clear=False)` | Tail recent logcat output (real-time debug) |
| `android_a11y_audit(token, limit=12)` | **Recon.** Structural a11y from uiautomator: clickable elements with no text/desc, undescribed images, sub-48dp touch targets. No contrast / TalkBack order. |
| `android_perf_snapshot(token, package="")` | **Recon.** Cold-start (`am start -W`), memory (PSS via `dumpsys meminfo`), frame jank (`dumpsys gfxinfo`), each banded. Single sample — not a benchmark. |

Android locator strategies: `text`, `accessibility_id` (content-desc), `resource_id` (e.g. `com.example:id/loginButton`), `xpath`.

**Why adb-direct instead of Appium for Android?** No npm install needed (works on networks that block public package registries), no Appium server process to manage, simpler stack. Trade-off: no synchronization layer like Appium's, so flaky-test patterns are slightly different.

## What the agent can do (prompt → tools)

| What you want to do | What the agent will use |
|---|---|
| First-pass recon of a URL | `web_recon(url)` — or `web_recon(url, session_name=...)` for the logged-in app; or the `auto-discover-recon` skill for flow-walking too |
| First-pass recon of an APK | `apk_inspect` + `apk_security` — static, no device; then install + `android_a11y_audit` / `android_perf_snapshot` for runtime |
| First-pass recon of an IPA | `ipa_inspect(ipa_path)` — static, no device; then install + `ios_a11y_audit` / `ios_perf_snapshot` for runtime |
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
| Tail iOS device logs | `ios_logs(token, log_type="syslog")` — call repeatedly to follow |
| Test an Android app | `device_allocate(platform="android", emulator_name="Pixel_10_Pro_XL", package="com.android.settings")` → `android_inspect` → `android_tap` / `android_type` / `android_assert_*` → `device_release` |
| Tail Android device logs | `android_logcat(token, filter_expr="MyApp:V *:S", lines=200)` — call repeatedly to follow |

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

### Android prerequisites (only if you'll use the `android_*` tools)

1. **Android Studio** with the **Android SDK** + at least one **AVD** (Android Virtual Device). Easiest: install Android Studio from https://developer.android.com/studio, run it once, let it install the SDK to the default path (`~/Library/Android/sdk` on macOS), then create an AVD via Tools → Device Manager.
2. **`adb` discoverable.** The driver looks in this order: `which adb`, `$ANDROID_HOME/platform-tools/adb`, `$ANDROID_SDK_ROOT/platform-tools/adb`, `~/Library/Android/sdk/platform-tools/adb`. If none match, set `ANDROID_HOME` or add platform-tools to your `PATH`.
3. **No npm, no Appium needed.** Everything goes through `adb` directly.
4. **For `apk_inspect` only:** the SDK **build-tools** (they provide `aapt`/`aapt2`). Installed by default with Android Studio; the tool searches `PATH` then `$ANDROID_HOME/build-tools/<newest>/`. No device or emulator required for `apk_inspect`.

Verify Android prereqs:
```bash
adb version                       # or ~/Library/Android/sdk/platform-tools/adb version
~/Library/Android/sdk/emulator/emulator -list-avds   # at least one AVD
aapt2 version                     # or $ANDROID_HOME/build-tools/<ver>/aapt2 version  (for apk_inspect)
```

The AVD doesn't need to be running before `device_allocate` — pass `emulator_name=<your AVD>` and the driver will boot it for you (~30-90s on first cold boot).

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
Use qa-execution.web_recon on https://example.com and summarize the first-pass findings.
```

```
Use qa-execution.apk_inspect on /path/to/app.apk and summarize identity, permissions, and security flags.
```

```
Use qa-execution: device_allocate platform=android emulator_name=Pixel_10_Pro_XL
package=com.android.settings, then android_a11y_audit, then android_perf_snapshot,
then device_release.
```

```
Use qa-execution.test_run to execute mcp-servers/qa-execution/tests/web/example-login.yaml.
```

```
Use qa-execution: device_allocate platform=ios bundle_id=com.apple.mobilesafari,
then ios_inspect, then ios_screenshot, then device_release.
```

```
Use qa-execution: device_allocate platform=android emulator_name=Pixel_10_Pro_XL
package=com.android.settings, then android_inspect, then android_screenshot,
then android_logcat lines=50, then device_release.
```

## Where state lives

- **Screenshots** — `~/qa-screenshots/<timestamp>.png` by default
- **Saved sessions** — `~/.qa-execution/sessions/<name>.json` (contains auth cookies — keep private)
- **Test artifacts** — wherever your YAML test specifies via `screenshot.path`

## Roadmap

- **v0.1**: web + API, headless Chromium, single page session, YAML test runner
- **v0.2**: iOS Simulator via Appium (`device_*` + `ios_*` tools)
- **v0.3**: Android emulator via direct `adb` (`android_*` tools, no Appium), `ios_logs` for iOS debug parity
- **v0.4**: web auto-discovery recon (`web_recon`, `web_discover`, `web_a11y_audit`, `web_perf_snapshot`, `security_headers_check`) — first-pass mapping across functionality / UI / accessibility / performance / security; session-aware (`web_recon` loads a saved auth session)
- **v0.5**: mobile/APK recon — `apk_inspect` (static, no device), `android_a11y_audit`, `android_perf_snapshot`, `ios_a11y_audit`. Layer 2 spans web **and** mobile.
- **v0.6** (current): deep APK security (`apk_security` — per-component exported flags, cleartext, backup), IPA static inspection (`ipa_inspect`), iOS cold-launch perf (`ios_perf_snapshot`)
- **v0.7**: iOS on-device memory & frame timing (Instruments/xctrace), deep APK/iOS binary analysis (MobSF-class), CLI testing (`cli_*`), Chrome extension testing, real-device farm integration, mobile YAML runner
- Later: multiple tabs, headful toggle, request mocking/interception, video recording, parameterized tests

## Limitations (v0.3)

- Single browser context per server process. Closing the server discards in-memory state — use `web_session_save` first if you need it back.
- Network logs capture response metadata (status, method, URL) — not bodies.
- No request mocking yet.
- Browser is headless only — you'll see what's happening via screenshots and logs.
- `api_request` supports JSON bodies only. Raw text/binary support is roadmap.
- **iOS**: Simulator only (no real devices yet). Appium server runs externally — the MCP does not start/stop it.
- **Android**: emulator preferred; physical devices work too if listed by `adb devices`. The `android_type` clear-field uses 100 backspaces (simple, works across versions, but slow for large fields). Scrolling is swipe-based, not list-aware — for long lists, scroll repeatedly + inspect between scrolls.
- **YAML test runner** (`test_run`) covers web + API only. Mobile actions in YAML are roadmap (v0.4) — for mobile tests today, drive the `ios_*` / `android_*` tools directly.

## Troubleshooting

**`playwright install chromium` fails**: ensure you're in the same environment where you installed the package. With venv: `source .venv/bin/activate` first. With uv tool: use `uv tool run playwright install chromium`.

**Tools don't appear in Claude**: check `claude mcp list`. If `qa-execution` is missing, re-run `claude mcp add`. If listed but tools don't show, restart your Claude Code session.

**Browser fails to launch**: on Linux you may need `playwright install-deps`. On macOS this is usually fine.

**`api_request` times out**: the default timeout is 30s. For long-running endpoints, file an issue or fork to extend.
