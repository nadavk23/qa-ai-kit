# RECOVERY — restoring this toolkit on a fresh machine

Steps to bring QA AI KIT back to a working state after a machine reformat or move.

## 1. Prerequisites

Install on the new machine:

- **Python 3.10+** — `python3 --version` to confirm. macOS bundles 3.9 sometimes; install 3.10+ via `brew install python@3.11` if needed.
- **git** — already on most systems
- **Claude Code** — install from https://docs.claude.com/en/docs/claude-code
- **gh CLI** *(optional, makes cloning private repos easier)* — `brew install gh && gh auth login`
- **uv** *(optional, faster Python install path)* — `brew install uv`

## 2. Clone this repo

```bash
mkdir -p "$HOME/Projects"
cd "$HOME/Projects"
gh repo clone nadavkatz/qa-ai-kit "QA AI KIT"
# Or via plain git if you don't have gh:
# git clone git@github.com:nadavkatz/qa-ai-kit.git "QA AI KIT"
cd "QA AI KIT"
```

## 3. Restore the `review-test-plan` skill to personal scope (optional)

The skill is already in `.claude/skills/review-test-plan/` so it works automatically when Claude Code opens this folder. If you want it available from **any** folder on this machine, also copy it to your personal skills directory:

```bash
mkdir -p "$HOME/.claude/skills"
cp -R ".claude/skills/review-test-plan" "$HOME/.claude/skills/"
```

## 4. Restore the qa-execution MCP server

### Option A — venv (most reliable)

```bash
cd "$HOME/Projects/QA AI KIT/mcp-servers/qa-execution"
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
claude mcp add qa-execution -- "$HOME/Projects/QA AI KIT/mcp-servers/qa-execution/.venv/bin/python" -m qa_execution
```

### Option B — uv (faster)

```bash
cd "$HOME/Projects/QA AI KIT/mcp-servers/qa-execution"
uv tool install .
uv tool run playwright install chromium
claude mcp add qa-execution -- qa-execution
```

## 5. Verify

```bash
claude mcp list
```

You should see `qa-execution`. Restart any open Claude Code session.

Smoke test in Claude Code:

> Use qa-execution: ping, navigate to https://example.com, inspect it, and tell me the title.

If it returns `pong` and `Example Domain`, you're fully back.

## 6. What does NOT get restored from the repo (and what to do)

| Lost on reformat | How to handle |
|---|---|
| `~/.qa-execution/sessions/*.json` (saved login cookies) | Re-login through each app and run `web_session_save` again. |
| `~/qa-screenshots/*.png` | These are disposable test artifacts. Don't restore. |
| Claude Code global settings (`~/.claude/settings.json`) | Re-register MCP servers per step 4 above. Re-add any other personal MCPs from your own notes. |
| Saved Claude memory files in `~/.claude/projects/...` | If you had personal memory worth keeping, you should have backed up `~/.claude/` separately before format. Worth doing next time. |

## Pre-format checklist (for next time)

Before letting IT touch the machine again, run:

```bash
cd "$HOME/Projects/QA AI KIT"
git status                 # anything uncommitted?
git push                   # everything on remote?
```

And consider a one-time backup of:

```bash
~/.claude/                 # skills, memory, settings (excluding caches)
~/.qa-execution/sessions/  # only if any of those auth sessions are hard to recreate
```

A 30-second `tar -czf claude-backup.tgz ~/.claude` copied to iCloud / Dropbox covers you.
