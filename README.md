# QA AI KIT

Personal QA workspace for reviewing test plans and related QA work.

## Layout

- `reviewed-plans/` — completed plan reviews kept for reference
- `CLAUDE.md` — instructions Claude Code reads when a session opens here

## Skills used

- **`review-test-plan`** (lives in `~/.claude/skills/`) — auto-triggers when a test plan, test strategy, or QA approach doc is pasted, linked (Figma / Google Docs / Confluence / Notion / any URL), or pointed at as a file path. Returns structured feedback against personal QA standards and ISTQB CTFL + CT-MAT.

## How to use

1. Open Claude Code with this folder as the working directory.
2. Ask: *"review this test plan"* and paste / link the plan, or pass a file path.
3. The skill returns: Must-fix / Should-fix / Nice-to-have / What's strong / Suggested next revision.
4. Save the review into `reviewed-plans/<feature-or-team>-<YYYY-MM-DD>.md` so you can compare across iterations.
