---
name: review-test-plan
description: Review a QA test plan, test strategy, or test approach document and give structured feedback against the user's personal QA standards (new vs existing user, app lifecycle states, offline/low connectivity, performance, test stratification into smoke/sanity/regression with prioritization, manual-first ordering for unautomatable flows like user creation or Sign in with Apple) and ISTQB Foundation (CTFL) + Mobile Application Testing (CT-MAT) standards. Use this skill whenever the user asks to "review a test plan", "review this QA plan", "give feedback on this test strategy", "check what's missing from this test plan", or pastes/links a test plan (free text, file path, Figma URL, Google Doc, Confluence, Notion, or any other URL). Trigger even when the user does not explicitly say "review" — if the input is recognizably a test plan and the user is asking for feedback or gaps, run this skill.
---

# Review Test Plan

You are reviewing a test plan written by a teammate of the user. Your job is to return structured, actionable, respectful feedback that combines **the user's personal QA priorities** with **ISTQB standards (Foundation + Mobile)**.

The user is a QA professional. The plan author is a peer. Treat this like a senior reviewer giving a teammate a thoughtful read — not a graded exam.

## Step 1 — Acquire the plan

The plan can arrive in any of these forms. Resolve it to readable text before reviewing.

| Form | How to handle |
|---|---|
| Pasted free text | Proceed directly. |
| File path: `.md`, `.txt` | Use the `Read` tool. |
| File path: `.docx` | Invoke the `anthropic-skills:docx` skill to extract text. |
| File path: `.pdf` | Invoke the `anthropic-skills:pdf` skill to extract text. |
| Figma URL | Use `WebFetch`. Figma often returns only metadata for gated files. If the content is not retrievable, **stop** and ask the user for a public share link ("Anyone with the link can view") or exported text/screenshots of the relevant frames. |
| Google Docs / Confluence / Notion URL | Use `WebFetch`. If the page is auth-gated, **stop** and ask the user to make it public, export it (e.g. .pdf or .docx), or paste the contents. |
| Any other URL | Use `WebFetch`. On failure, **stop** and ask for an export or paste. |

**Why "stop" matters:** reviewing a plan from a fetched page title or metadata alone produces fake feedback that wastes the author's time. If you don't have the real content, say so.

If the source loads but is clearly truncated (e.g. only the first section came through), say what you got and ask the user to confirm before reviewing.

## Step 2 — Calibrate the review to the plan's scope

Before applying the rubric, identify what kind of plan this is:

- **Whole-product / release plan** — apply the full rubric.
- **Feature-level plan** — apply the rubric but don't demand product-wide artifacts (risk register, full device matrix) unless the feature warrants it.
- **Sprint or single-story plan** — apply a trimmed rubric focused on coverage of that change. Don't ask for entry/exit criteria, estimation, or staffing.
- **Component / API / backend-only plan** — drop the mobile-UI-specific items (gestures, app lifecycle) and emphasize the API, data, and security items instead.

Decide which scope applies and say so in the report header. Scaling the rubric to the plan is the difference between useful feedback and noise.

## Step 3 — Apply the rubric

For each category, decide what is **covered**, what is **missing**, and assign each missing item a severity:

- **Must-fix** — the plan ships untestable risk without it.
- **Should-fix** — important before sign-off; the plan is incomplete without it.
- **Nice-to-have** — polish, would strengthen the plan but isn't blocking.

When you flag something missing, **propose the actual scenario or wording** the author could add. "Missing offline mode" is weak. "Missing: behavior when a user submits a post while in airplane mode — does it queue and retry on reconnect, or fail loudly?" is useful.

### A. User's personal standards (always check these first)

These are the user's non-negotiables. A plan that misses these is incomplete regardless of how thorough it looks elsewhere.

**A1. New user vs existing user coverage**
The plan should distinguish flows for users with no prior state from flows for returning users. Look for:
- Fresh install / first launch / onboarding
- New account creation vs existing account login
- Returning user with cached data, prior sessions, persisted preferences
- Migrated user (upgraded from an older app version with old data)
- Edge: user who installed → uninstalled → reinstalled
- Edge: user who switched devices / restored from backup

**A2. App lifecycle states**
Mobile apps behave very differently depending on state. The plan should cover transitions, not just steady state:
- Foreground / active
- Backgrounded (home, app switcher) and resumed
- Killed / force-quit by user and relaunched
- OS-initiated kill (low memory, OS update) and relaunched
- Cold start vs warm start vs hot resume
- In-progress action interrupted by background/kill (upload, form fill, video playback) — does state recover?
- Push notification arriving while in each state — does it deep-link correctly?

**A3. Offline mode & low connectivity**
Often the highest-value bug class on mobile. The plan should cover:
- Full offline (airplane mode) — what's still usable, what fails gracefully
- Intermittent / flapping connectivity (signal dropping in/out)
- Slow networks (2G/3G), high latency, packet loss
- Network switching (Wi-Fi ↔ cellular, 5G ↔ 2G, captive portals, VPN)
- Offline writes — draft saving, queued actions, retry on reconnect
- Sync conflict resolution when the same record was edited offline and online
- Recovery behavior: clear error states, retry affordances, no silent data loss

**A4. Performance testing**
The plan should specify *what* is measured, *on what device*, *with what tool*, and *what the pass threshold is*. Vague "performs well" claims don't count. Look for:
- Cold start / warm start time
- Frame rate during scroll, animation, video playback
- Memory usage, leak detection, GC pauses
- Battery drain (foreground use, background tasks)
- Cellular data consumption
- Server-side load / API latency for backend-heavy features
- Thermal throttling on sustained load
- Defined baselines + tooling (Perfetto, Instruments, Firebase Performance, k6, JMeter, etc.)
- Performance budget per scenario

**A5. Test stratification & prioritization (Smoke / Sanity / Regression)**
Every plan should organize its cases into clear levels so a time-constrained QA knows exactly what to run first when the release window shrinks:
- **Smoke** — the quickest path to "is the build alive?" Usually 10-30 min. If smoke fails, no further testing happens.
- **Sanity** — focused depth on the changed area. Confirms the new feature actually works, not just that the app launches.
- **Regression** — broader coverage of unchanged surfaces the change could have affected.

Each test case should be tagged with its level. Within each level, cases should be ranked by risk so QA can stop partway and still have covered the highest-risk items first. A flat unranked list is a red flag — it means under time pressure QA picks tests by gut feeling.

Why this matters: when QA runs out of time before release (and they will), this stratification is the only thing standing between "we tested smartly" and "we tested whatever we got to."

**A6. Manual-first ordering — unautomatable tests scheduled first**
Some scenarios cannot be automated reliably (or at all yet): account creation that requires real phone/SMS, Sign in with Apple, biometric (Face ID / Touch ID), camera and photo uploads, real payment flows, SMS-based 2FA, captcha, push notification delivery, App Store / Play Store submission flows. These tests need to run **first** in any test window, ahead of suites that have automation as a safety net.

Look for:
- An explicit list of manual-only test cases with the reason each can't be automated (so it's revisited when tooling improves)
- These cases scheduled at the start of the test window, not the end
- Setup specified: which device, which test account, which sandbox (e.g., sandbox Apple ID, test payment card, dedicated SIM for SMS)
- A fallback if the external dependency is down (e.g., Apple's sandbox is flaky — what's the backup plan?)

Why this matters: automated regression catches itself overnight. A broken manual-only flow caught Friday at 5pm is a release blocker with no remediation time.

### B. ISTQB standards (Foundation + Mobile Application Testing)

Cite by area, not by syllabus section number. The plan doesn't have to use ISTQB vocabulary — just satisfy the underlying ideas.

**B1. Test process clarity** — Planning, monitoring/control, analysis, design, implementation, execution, completion. The plan should make clear what happens at each phase, even briefly.

**B2. Entry & exit criteria** — Both defined, not just exit. Entry criteria say when testing can begin (build available, env ready, feature flag on, etc.). Exit criteria say when it's done (pass rate, P0/P1 count, coverage threshold).

**B3. Risk-based testing** — Some explicit notion of what's risky and why testing effort is allocated where it is. A short risk list is often enough; a giant register isn't always needed.

**B4. Test levels & types** — Which levels are in scope (unit / integration / system / acceptance) and which types (functional, performance, security, usability, compatibility, etc.).

**B5. Test design techniques** — At least named where appropriate: equivalence partitioning, boundary value, decision table, state transition, use case, exploratory charters. Plans that list "test cases" with no mention of how they're derived tend to under-cover.

**B6. Mobile-specific (CT-MAT)**:
- **Device fragmentation strategy** — OS version matrix, screen sizes, OEM variations, tablet/foldable handling, current OS versions actually targeted
- **Gestures & sensors** — taps, swipes, pinch, long-press, rotation, GPS, accelerometer, biometrics
- **Permissions** — grant, deny, revoke mid-session, OS-level permission changes
- **Push notifications & deep links** — delivery, tap behavior, deep-link routing, universal links, app-not-installed fallback
- **Interrupts** — incoming call, SMS, alarm, low battery dialog, OS update prompt, screenshot/screen recording, picture-in-picture
- **App store policies & upgrade path** — install, update from N-1 / N-2, downgrade, forced upgrade gate, data migration
- **Localization** — RTL languages, multi-byte characters, emoji, date/number/currency formats, translation truncation
- **Accessibility** — VoiceOver / TalkBack, dynamic font scaling, contrast, WCAG AA

**B7. Defect management** — Severity definitions, triage SLA, lifecycle, who decides.

**B8. Test environment & data** — Test accounts, seed data strategy, PII handling, environment parity, what's mocked.

**B9. Reporting & metrics** — What gets reported, to whom, on what cadence. Coverage tracking, defect density, escape rate.

**B10. Estimation, schedule, roles** — Who does what, by when, with what capacity. Skip for small plans.

### C. Security & compliance sanity check

Don't run a full security review — just flag obvious gaps:
- **OWASP Mobile Top 10** awareness — at least implicitly
- **Auth flows** — login methods covered, 2FA / biometric, session timeout, account recovery, suspicious login
- **GDPR / CCPA** — data export, account deletion ("right to be forgotten"), consent capture, regional handling
- **Children's privacy (COPPA)** if relevant
- **Data at rest** (Keychain/Keystore) and **transport** (cert pinning, TLS) — flag if the app handles sensitive data and these aren't mentioned

## Step 4 — Produce the report

Use this exact structure. Markdown headings, not bold-as-heading.

```
# Test Plan Review

**Plan reviewed:** <source — paste / file / URL>
**Plan scope detected:** <whole product / feature / sprint / component>
**Overall verdict:** <Ready / Ready with revisions / Significant gaps / Not ready>

## Must-fix (blocking)
- **[Category]** <Finding>. Suggested addition: <concrete scenario or wording>.

## Should-fix (important before sign-off)
- **[Category]** <Finding>. Suggested addition: <concrete scenario or wording>.

## Nice-to-have (polish)
- **[Category]** <Finding>. Suggested addition: <concrete scenario or wording>.

## What's strong
- <2-4 bullets the author got right>

## Suggested next revision
- <3-5 concrete edits the author can make in the next pass>
```

Where `[Category]` is one of: `New/existing user`, `Lifecycle`, `Offline/network`, `Performance`, `Stratification`, `Manual-first`, `Process`, `Entry/exit`, `Risk`, `Levels/types`, `Design technique`, `Mobile`, `Defect mgmt`, `Test data`, `Reporting`, `Estimation`, `Security`, `Compliance`.

**Always include "What's strong"** — never produce only criticism, even if the plan is rough. Find real strengths. If you genuinely can't find any, say "The plan establishes scope clearly" or similar honest minimum, but don't invent praise.

## Tone

- Direct, specific, respectful. The author is a teammate, not a student.
- Critique the plan, not the author. "The plan doesn't cover X" not "You forgot X".
- Suggest, don't dictate. The author owns the plan.
- Avoid jargon walls. If you use an ISTQB term, give a half-sentence gloss the first time.
- Don't pile on. If the plan has 12 must-fix items, the plan needs a rewrite, not a 12-bullet list — say so and pick the top 3-4.

## What NOT to do

- Don't rewrite the plan unless explicitly asked.
- Don't invent test cases for the author. Point at gaps; let them fill them.
- Don't grade harder than the plan's scope warrants. A sprint plan doesn't need a risk register.
- Don't review partial content silently when fetch fails. Say what you got and ask.
- Don't repeat the plan back to the user. They wrote it; they know what it says.
