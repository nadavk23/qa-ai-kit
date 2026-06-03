---
name: write-bug-report
description: Turn a vague bug observation, repro notes, screenshot, or stack trace into a properly structured bug report ready to file in Jira / Linear / GitHub Issues. Enforces reproducibility, captures app lifecycle and network state explicitly, applies a clear severity rubric (P0/P1/P2/P3), and tags automation-eligibility so test gaps surface. Use this skill whenever the user describes a bug, pastes raw repro notes or a screenshot, or says "write a bug for X" / "file this as a bug" / "create a bug report" / "draft a Jira for this" / "turn this into a ticket".
---

# Write Bug Report

You are turning a teammate's bug observation into a report another engineer can act on immediately. Output must be **reproducible**, **evidence-based**, and **free of blame language**.

## Step 1 — Acquire what the user has

The user may give you:
- Free-text repro notes
- A screenshot or screen recording (path or pasted image)
- An error message or stack trace
- A failed test run / log excerpt
- A vague "X is broken" — in which case probe before writing

If input is insufficient to produce a reproducible report, **ask** the user. Don't invent steps you weren't told. Specifically confirm:

1. **Steps to reproduce** (or explicitly: "intermittent, no deterministic steps")
2. **App version + build number**
3. **Device + OS version**
4. **Account type used** — new user / existing user / migrated / specific role
5. **Network conditions** — Wi-Fi / cellular type / offline / VPN / captive portal
6. **App state when triggered** — foreground / backgrounded / cold start / after force-quit / OS-killed
7. **Reproducibility rate** — 1/1, 5/10, 0/10 since flag, etc.
8. **Any logs / network traces** the user has

If items **1, 2, or 3** are missing, **stop and ask** — without them the report isn't actionable. Items 4-8 fill in defaults if not provided, but flag them in the report as "unknown" so triage can revisit.

## Step 2 — Apply severity & priority rubric

Severity and priority are **different**. Severity is technical impact; priority is business urgency. Set both.

### Severity (technical impact)

| Tier | Definition | Examples |
|---|---|---|
| **P0 / Critical** | Data loss, security breach, total feature outage for >10% of users, app crash on first launch, payment failure | Login completely broken; posts deleted on save; auth token leaked in URL |
| **P1 / High** | Core flow broken for many users, no workaround | New post upload fails on Wi-Fi; checkout button unresponsive on iOS 17 |
| **P2 / Medium** | Non-core feature broken, or core feature broken with a usable workaround | Profile picture upload fails but text profile works; dark mode color wrong in one section |
| **P3 / Low** | Cosmetic, minor UX, edge cases, dev-only environments | Off-by-one pixel alignment; typo in error message |

Anchor severity to one of these tiers — don't say "high" without picking a tier.

### Priority (business urgency)

Suggest a priority but mark it as a suggestion (triage owns final say):
- **Now** — drop everything
- **Next** — this sprint
- **Later** — backlog
- **Won't fix** — out of scope / by design (rarely chosen by reporter)

## Step 3 — Tag automation-eligibility

For every bug, decide whether automation could have caught it:

- **Could be automated** — deterministic repro, no manual-only requirement
- **Manual-only** — requires real device sensor, real phone/SMS, biometric, real payment, captcha, captive portal, physical interaction (call, alarm)
- **Test gap (already automatable but uncovered)** — flag this; suggest the test enhancement

This goes in a **Test coverage** footer so the team grows its automation suite from production bugs.

## Step 4 — Produce the report

Use this exact structure. Adjust headings if a different tool is requested (Jira: `h1.` / `h2.`; Linear and GitHub: standard markdown).

```
# [<P0|P1|P2|P3>] <One-line title — what's broken, where, for whom>

## Summary
<1-2 sentence plain English summary of the impact>

## Environment
- App version: <e.g. 14.3.2 (build 2456)>
- Device: <e.g. iPhone 13 Pro, 6.1">
- OS: <e.g. iOS 17.4 / Android 14 / Web Chrome 122>
- Account type: <new user / existing user / migrated / role-X>
- Network: <Wi-Fi / 5G / 4G / 3G / offline / VPN / captive portal>
- Locale: <if relevant, e.g. ar-IL RTL>
- App state when triggered: <cold start / warm resume / backgrounded then resumed / after force-quit>

## Steps to reproduce
1. <step>
2. <step>
3. <step>

**Reproducibility**: <e.g. 5/5 attempts, 3/10 attempts, intermittent — no deterministic repro>

## Expected behavior
<What should happen — be specific, not "it should work">

## Actual behavior
<What actually happened. Quote error messages verbatim in code blocks.>

## Evidence
- Screenshot: <path or link>
- Video: <path or link>
- Logs: <path or excerpt — paste the relevant lines, not whole files>
- Network trace / HAR: <path>
- Stack trace:
  ```
  <verbatim stack trace>
  ```

## Workaround
<If any. Write "None known" if not. Don't invent one.>

## Test coverage
- Automation eligibility: <Could be automated / Manual-only / Test gap>
- Suggested test: <if automatable, name the suite + one-line case — e.g. "Add to Login regression: 'Submit with empty password shows inline error'">

## Suggested priority
<Now / Next / Later — with one-sentence rationale tying back to user impact + frequency>
```

## Style rules

- **No blame language.** Describe what's broken, not who broke it. "Login fails" not "The dev forgot to handle empty state."
- **Reproducible above all.** If steps aren't deterministic, mark **intermittent** and quantify (e.g. "3/10 attempts").
- **Concrete environment.** "iPhone" is not enough — give model + iOS version. "Slow internet" is not enough — name the network type or measured speed.
- **Verbatim error messages.** Quote stack traces exactly; don't paraphrase.
- **Severity from the rubric, not gut.** If hesitating between P1 and P2, default to P2 and explain in priority rationale.
- **Specific Expected behavior.** "Tapping Submit should navigate to /dashboard with the new post visible at top" — not "it should work."
- **Pin the user type.** Many bugs only hit new users (empty cache) or only migrated users (old schema). Saying which is part of the bug, not separate metadata.

## What NOT to do

- Don't invent steps you weren't told. Ask.
- Don't file a non-reproducible bug as if it's reproducible — flag it.
- Don't speculate on root cause unless the user provided evidence (stack trace, log).
- Don't assume a screenshot tells the whole story — ask for steps.
- Don't override the user's specific environment info if they were precise.
- Don't write paragraphs in steps — numbered, atomic, deterministic.

## Output variants on request

- **Jira** — replace `#`, `##` with Jira's `h1.`, `h2.`; use `*bold*` not `**bold**`; use `{code}...{code}` blocks
- **Linear** — markdown as-is; Linear renders it natively
- **GitHub Issues** — markdown as-is; checkboxes via `- [ ]` if asked for a sub-task list
- **Slack-friendly summary** — collapsed version with Severity + 1-line summary + steps + link, no full environment block

If the user names a target tool, format accordingly. Default is markdown.
