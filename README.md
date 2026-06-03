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

### MCP servers

| Server | Version | Tools | Surfaces covered |
|---|---|---|---|
| **`qa-execution`** | 0.2.0 | 26 | Web (Playwright) · API (httpx) · iOS Simulator (Appium) |

**`qa-execution` tool breakdown:**
- **Web + API (15)** — `ping`, `web_navigate`, `web_inspect`, `web_click`, `web_type`, `web_assert_text`, `web_assert_element`, `web_screenshot`, `web_wait`, `web_logs`, `web_session_save`, `web_session_load`, `web_batch`, `api_request`, `test_run`
- **iOS (11)** — `device_allocate`, `device_release`, `device_list`, `ios_tap`, `ios_type`, `ios_assert_element`, `ios_assert_text`, `ios_inspect`, `ios_screenshot`, `ios_wait`, `ios_scroll`

Roadmap: Android (v0.3), CLI + Chrome extension testing (v0.4). See [`mcp-servers/qa-execution/README.md`](mcp-servers/qa-execution/README.md) for the full tool reference.

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
| Run a web test | *"use qa-execution to navigate to X, type Y, assert Z"* |
| Run an iOS test | *"device_allocate platform=ios bundle_id=com.apple.mobilesafari, then ios_inspect"* |
| Restore the kit on a new machine | Follow [`RECOVERY.md`](RECOVERY.md) |

## See also

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — long-term direction: capabilities behind a single MCP Gateway for external integrations (Jira / Slack / GitHub / etc.)
- [`RECOVERY.md`](RECOVERY.md) — bring the kit back on a freshly reformatted machine
- [`mcp-servers/qa-execution/README.md`](mcp-servers/qa-execution/README.md) — full reference for every `qa-execution` tool, including iOS locator strategies and YAML test schema
