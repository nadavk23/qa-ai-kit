---
name: auto-discover-recon
description: Point the kit at a live web URL (or a running mobile app) and produce a first-pass auto-discovery map across five dimensions — functionality, UI, accessibility, performance, and security. Walks the real/main flows, captures evidence, and returns a prioritized "where to go deeper" list. Use this skill whenever the user says "recon this", "auto-discover", "scan this URL/app", "map this product", "give me a first pass on X", "what should I test here", or pastes a URL/APK and asks what's worth testing. This is breadth-first triage, NOT a full audit. Trigger even when the user doesn't say "recon" — if they hand over a live target and want a first read on quality risks, run this skill.
---

# Auto-discovery recon (Layer 2)

You are pointing QA AI KIT at a **live target** and returning a first-pass map of
what exists and where the quality risk is. The goal is triage, not a full audit:
enough signal to prove value and to decide where a deeper pass is worth it.

This skill orchestrates the `qa-execution` MCP recon tools. It does **not**
replace them — it drives them in a sensible order, walks the main flows a static
scan can't reach, and synthesizes one prioritized report.

## Guardrails — read first

- **Only test targets the user is authorized to test.** If the target isn't
  obviously the user's own product or a public demo site, ask before proceeding.
  Recon touches accessibility, performance, and security surfaces — treat it like
  any other testing-with-permission activity.
- **This is a first pass, not a guarantee.** Every dimension here is deliberately
  shallow. Never present recon output as "the site is secure/accessible/fast" —
  present it as "here's the first-pass signal and here's where to look harder."
- **Read-only by default.** Discovery, a11y, perf, and header checks are safe.
  Walking a flow may submit forms — do NOT submit destructive actions (delete,
  purchase, send) on a target you don't own, and never enter real credentials or
  real payment data. Use obviously-fake test data and say so.
- **Don't invent findings.** Report what the tools returned. If a dimension
  couldn't run (no browser, gated URL, mobile not set up), say so plainly.

## Step 1 — Identify the target and confirm authorization

Resolve what you were handed:

| Target | Path |
|---|---|
| Web URL (`http(s)://…`) | Web recon — Steps 2–4. This is the fast, fully-supported path. |
| `.apk` file / running Android app | Mobile recon — Step 5. Requires an emulator/device set up (see `qa-execution` README). |
| `.ipa` / iOS app | Mobile recon — Step 5, iOS variant. Requires Appium running. |
| A product *description* with no live target | Wrong skill — this is Layer 1 territory. Point them at `diagnose-and-recommend` (placeholder) or offer `review-test-plan`. |

If authorization is at all unclear, ask one direct question before running.

## Step 2 — Static sweep (web)

Run the one-shot first, then decide where to zoom in:

1. `web_recon(url)` — navigates (with a settle for client-rendered apps) and
   returns discovery + accessibility + performance + security in one
   consolidated report.

That single call covers the static dimensions. Read its output before going
further — the discovery section tells you which flows exist and are worth
walking in Step 3.

**Watch for a login wall.** Most real products show almost nothing until you're
authenticated — a sparse `web_discover` result dominated by a login/signup form
is the tell. When you see that, the unauthenticated recon is only the *front
door*; the real surface is behind auth. Go to Step 2a before drawing conclusions.

If you need to re-run a single dimension (e.g. after navigating deeper into the
app), the individual tools are: `web_discover`, `web_a11y_audit`,
`web_perf_snapshot`, `security_headers_check(url)`.

## Step 2a — Authenticated recon (the login → save → re-scan loop)

This is where the real value is for any product with accounts. Do NOT skip it
just because the front-door recon returned *something*.

1. Ask the user for test credentials (or a way to reach a logged-in state). If
   they can't/won't provide them, say so and report only the unauth surface.
2. Walk the login flow once: `web_navigate` → `web_inspect` → `web_type` the
   credentials → `web_click` submit → `web_assert_*` a logged-in marker.
3. `web_session_save("recon-auth")` to persist the authenticated cookies.
4. Re-run recon against a deep, logged-in URL **through that session**:
   `web_recon(<in-app URL>, session_name="recon-auth")`. Now discovery, a11y,
   perf, and security map the actual app, not the marketing shell.
5. Compare the two passes in the report — front-door vs. authenticated. The
   delta is usually the whole story.

Never use real end-user credentials or real payment data. Use dedicated test
accounts the user provides.

## Step 3 — Walk the main flows (web)

Static discovery finds the *surface*; the real value is walking 1–3 **main
flows** the product is actually built around. From the `web_discover` output,
pick the highest-signal flows — usually the forms and primary-nav destinations.
Typical candidates: sign-up / login, search, primary create action, checkout.

For each flow you walk:
1. `web_navigate` to the entry point (or click into it).
2. `web_inspect` to find selectors.
3. Drive it with `web_type` / `web_click` using **fake test data** (e.g.
   `recon+test@example.com`). Stop before any irreversible action.
4. `web_assert_text` / `web_assert_element` on the expected outcome.
5. `web_screenshot` at the key step for evidence.
6. `web_logs` after the flow — console errors and failed network calls during a
   real flow are high-signal functionality findings.
7. Re-run `web_a11y_audit` / `web_perf_snapshot` on the deeper screen if it
   differs materially from the landing page (logged-in dashboards often do).

Keep it to the 1–3 most important flows. Breadth over depth — this is recon.

## Step 4 — Synthesize the web report

Return the report in the structure below.

## Step 5 — Mobile recon (Android / iOS)

Only if the target is an app and a device is available. This path is thinner
than web — there is no one-shot mobile recon tool yet; you orchestrate the
existing device tools.

1. `device_allocate` (Android: `platform=android`, `emulator_name`, `package`;
   iOS: `platform=ios`, `bundle_id` or `app`).
2. `android_inspect` / `ios_inspect` — the mobile analog of `web_discover`:
   enumerate the on-screen elements and locators.
3. `android_screenshot` / `ios_screenshot` — UI evidence.
4. Walk the app's main flow with `*_tap` / `*_type` / `*_assert_*`, same
   fake-data discipline as Step 3.
5. `android_logcat` / `ios_logs` — crashes, ANRs, and errors during the flow are
   the highest-signal mobile findings.
6. `device_release` when done.

**Mobile dimension coverage is partial and honest about it:**
- Functionality + UI: covered (inspect, screenshot, flow-walk, logs).
- Accessibility: only what `*_inspect` exposes (missing content-desc / labels).
  No structured a11y audit tool for mobile yet — flag as a gap.
- Performance: logcat/instruments signals only. No structured mobile perf
  snapshot yet — flag as a gap.
- Security: not covered on-device. Flag as a gap.

Log these gaps explicitly in the report's "Not covered" section — they're
exactly the feature-requests that feed the roadmap.

## Report format

```
# Auto-discovery recon — <target>

**Target:** <url / app + package>   **Date:** <YYYY-MM-DD>
**Scope:** First-pass triage. Not a full audit.

## Snapshot
<2–4 sentence read: what this product appears to be, main flows found, and the
single most important risk to look at first.>

## By dimension
### Functionality  — <flows found / walked, console+network errors seen>
### UI             — <screenshots captured, layout/rendering notes>
### Accessibility  — <FAIL/WARN counts from the audit, top issues>
### Performance    — <FCP / load / weight with bands>
### Security       — <headers pass/fail, HTTPS, cookies — surface only>

## Prioritized "go deeper" list
1. <highest-value next investigation, and which tool/approach — e.g. "run axe-core
   on the checkout screen", "k6 load test the search API", "OWASP ZAP the login">
2. ...

## Not covered (gaps → candidate feature-requests)
- <dimension/capability the kit couldn't assess, and why>
```

## After the report

- Offer to save it to `reviewed-plans/recon-<target-slug>-<YYYY-MM-DD>.md`
  (same convention as reviews). Confirm the filename first; don't save without
  asking.
- If recon surfaced a capability gap (mobile a11y, mobile perf, deep security,
  load testing), note it — this is the raw material for Layer 1's recommendation
  engine and the enterprise-tier roadmap. For now, just call it out in the
  report; the gap-capture log is a Layer 1 item.

## Tone

- Direct, specific, respectful. You're handing a teammate a triage map, not a
  verdict. Lead with the one thing worth looking at first.
- Be honest about shallowness. "First-pass" is a feature, not a hedge — say what
  you checked and what you didn't, every time.
