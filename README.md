# QA AI KIT

Personal QA toolkit — Claude Code skills + MCP servers for test plan review, bug reporting, test code generation, and test execution across web, API, and iOS.

## What's in the kit

### Skills

Auto-trigger inside Claude Code when their description matches your message. Installed in this repo at `.claude/skills/` (works when Claude Code opens this folder) and mirrored to `~/.claude/skills/` (works in any folder).

| Skill | Trigger phrases | Purpose |
|---|---|---|
| **`review-test-plan`** | "review this test plan" / paste or link a plan | Structured feedback against personal QA standards + ISTQB CTFL + CT-MAT. Returns Must-fix / Should-fix / Nice-to-have / What's strong / Suggested next revision. |
| **`write-bug-report`** | "write a bug for X" / "draft a Jira for this" / describe a bug | Asks incrementally for the critical missing info (steps, app version, device + OS) instead of dumping a long checklist. Outputs a P0–P3 ticket with reproducibility, lifecycle/network state, and automation-eligibility tag. |
| **`plan-to-pilot`** | "convert this plan to Pilot tests" / "generate Pilot code" | Emits runnable [Wix Pilot](https://github.com/wix-incubator/pilot) TypeScript specs using `pilot.autopilot()`. Defaults: `@wix-pilot/playwright` for web, `@wix-pilot/webdriverio-appium` for mobile (Detox as alternative for React Native). One spec file per feature under `./pilot-tests/<feature-slug>/`. |
| **`auto-discover-recon`** | "recon this URL" / "scan this app" / "what should I test here" / paste a live URL | **Layer 2.** Points the kit at a live web URL (or running app) and returns a first-pass map across functionality / UI / accessibility / performance / security — walks the main flows, captures evidence, and returns a prioritized "go deeper" list. Breadth-first triage, not a full audit. |
| **`diagnose-and-recommend`** | *(placeholder — Layer 1, not built)* | **Roadmap.** Will diagnose a product from a plain-language description and recommend which tools/MCPs to install (basic package + deeper modules on demand), logging capability gaps as feature-requests. Today it only explains the plan and routes you to what exists. |

### MCP servers

| Server | Version | Tools | Surfaces covered |
|---|---|---|---|
| **`qa-execution`** | 0.4.0 | 43 | Web (Playwright) · API (httpx) · iOS Simulator (Appium) · Android emulator (direct `adb`, no Appium) · Auto-discovery recon |

**`qa-execution` tool breakdown:**
- **Web + API (15)** — `ping`, `web_*` (12), `api_request`, `test_run`
- **Auto-discovery recon (5)** — `web_recon` *(one-shot)*, `web_discover`, `web_a11y_audit`, `web_perf_snapshot`, `security_headers_check` — first-pass across functionality / UI / accessibility / performance / security
- **Device session (3)** — `device_allocate`, `device_release`, `device_list` (cross-platform: iOS + Android)
- **iOS (9)** — `ios_tap`, `ios_type`, `ios_assert_element`, `ios_assert_text`, `ios_inspect`, `ios_screenshot`, `ios_wait`, `ios_scroll`, `ios_logs` *(real-time debug — log tail)*
- **Android (11)** — `android_tap`, `android_type`, `android_assert_element`, `android_assert_text`, `android_inspect`, `android_screenshot`, `android_wait`, `android_scroll`, `android_back`, `android_home`, `android_logcat` *(real-time debug — log tail)*

Roadmap: mobile recon tools, CLI + Chrome extension testing (v0.5), real-device farm integration. See [`mcp-servers/qa-execution/README.md`](mcp-servers/qa-execution/README.md) for the full tool reference.

## Layout

```
QA AI KIT/
├── .claude/skills/                 # Project skills (also mirrored to ~/.claude/skills/)
│   ├── review-test-plan/
│   ├── write-bug-report/
│   └── plan-to-pilot/
├── mcp-servers/
│   └── qa-execution/               # Test-execution MCP server (Playwright + httpx + Appium)
├── pilot-tests/                    # Generated Wix Pilot specs (output of plan-to-pilot)
├── reviewed-plans/                 # Saved test plan reviews
├── ARCHITECTURE.md                 # Capability + MCP Gateway architecture
├── RECOVERY.md                     # Restore the kit on a fresh machine
├── CLAUDE.md                       # Instructions Claude Code reads in this folder
└── README.md                       # You are here
```

## Prerequisites

### Required (everyone)

| Tool | Why | Install (macOS) |
|---|---|---|
| **Python 3.10+** | Runs the `qa-execution` MCP server | `brew install python@3.11` |
| **git** | Repo + commits | Usually preinstalled; otherwise `xcode-select --install` |
| **Claude Code** | Hosts the skills + MCP servers | https://docs.claude.com/en/docs/claude-code |

### Required for Android testing (only if you'll use the `android_*` MCP tools)

| Tool | Why | Install |
|---|---|---|
| **Android Studio + SDK** | Provides the emulator, `adb`, and AVD management | https://developer.android.com/studio (run once to install SDK) |
| **At least one AVD** | An emulator image to test against | Android Studio → Tools → Device Manager → Create Device |
| **`adb` discoverable** | The MCP looks in `which adb` / `$ANDROID_HOME/platform-tools` / `~/Library/Android/sdk/platform-tools` | Set `ANDROID_HOME` or add to `PATH` if not in defaults |

**No npm or Appium needed for Android** — the driver uses `adb` directly. This was a deliberate choice so the kit keeps working on corporate networks that block public package registries.

Verify Android prereqs:
```bash
adb version
~/Library/Android/sdk/emulator/emulator -list-avds   # at least one AVD listed
```

### Required for iOS testing (only if you'll use the `ios_*` MCP tools)

| Tool | Why | Install |
|---|---|---|
| **Xcode + Command Line Tools** | Provides the iOS Simulator and `xcrun simctl` | App Store, then `xcode-select --install` |
| **Node.js** | Runtime for the Appium server | `brew install node` |
| **Appium 2** | The mobile automation server `qa-execution` talks to | `npm install -g appium` |
| **xcuitest driver** | Appium driver for iOS Simulators | `appium driver install xcuitest` |
| **Appium server running** | The MCP does not manage its lifecycle — start it externally before invoking `ios_*` tools | `appium` (defaults to `http://127.0.0.1:4723`; override with `QA_APPIUM_URL`) |

Verify iOS prereqs:
```bash
node --version            # any LTS
appium --version          # 2.x
appium driver list --installed   # should include xcuitest
xcrun simctl list devices         # at least one iPhone runtime
```

> **Note on corporate networks:** `npm install -g appium` is commonly blocked by enterprise firewalls (e.g. on Wix laptops). If that's you, install Appium from a personal network for ~5 min — the Appium server itself runs locally afterward and needs no further network.

### Optional

| Tool | Why | Install |
|---|---|---|
| `gh` CLI | Cloning the repo, opening PRs | `brew install gh && gh auth login` |
| `uv` | Faster Python install path (alternative to venv) | `brew install uv` |

## Setup on a fresh machine

Full step-by-step lives in [`RECOVERY.md`](RECOVERY.md). Short version:

```bash
# 1. Clone
gh repo clone nadavk23/qa-ai-kit "$HOME/Projects/QA AI KIT"
cd "$HOME/Projects/QA AI KIT"

# 2. qa-execution MCP server (venv path — see RECOVERY.md for uv alternative)
cd mcp-servers/qa-execution
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
claude mcp add qa-execution -- "$PWD/.venv/bin/python" -m qa_execution
cd ../..

# 3. (Optional) Make skills work in any folder, not just this one
mkdir -p "$HOME/.claude/skills"
cp -R .claude/skills/* "$HOME/.claude/skills/"

# 4. (Only for iOS testing) Install Appium + driver, then run the server in a separate terminal
npm install -g appium
appium driver install xcuitest
appium    # leave running while you use ios_* tools
```

Then **restart Claude Code** so it picks up the new MCP server, and `claude mcp list` should show `qa-execution`.

## How to use

Open Claude Code with this folder as the working directory, then ask in natural language:

| What you want | Ask Claude… |
|---|---|
| Review a test plan | *"review this test plan"* + paste / link the plan |
| Write a bug report | *"write a bug for X"* + describe what broke (or paste a stack trace / screenshot) |
| Generate Pilot code from a plan | *"convert this plan to Pilot tests"* + paste / link a plan with cases |
| Recon a live target (Layer 2) | *"recon https://myapp.com"* / *"what should I test here?"* + a live URL |
| Run a web test | *"use qa-execution to navigate to X, type Y, assert Z"* |
| Run an iOS test | *"device_allocate platform=ios bundle_id=com.apple.mobilesafari, then ios_inspect"* |
| Run an Android test | *"device_allocate platform=android emulator_name=Pixel_10_Pro_XL package=com.android.settings, then android_inspect"* |
| Debug live (tail device logs) | *"call ios_logs"* / *"call android_logcat with filter MyApp:V \*:S"* |
| Restore the kit on a new machine | Follow [`RECOVERY.md`](RECOVERY.md) |

## See also

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — long-term direction: capabilities behind a single MCP Gateway for external integrations (Jira / Slack / GitHub / etc.)
- [`RECOVERY.md`](RECOVERY.md) — bring the kit back on a freshly reformatted machine
- [`mcp-servers/qa-execution/README.md`](mcp-servers/qa-execution/README.md) — full reference for every `qa-execution` tool, including iOS locator strategies and YAML test schema
