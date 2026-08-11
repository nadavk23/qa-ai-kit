# QA AI KIT — Claude Code context

This workspace is a QA toolkit: reviewing test plans against the user's personal QA standards and ISTQB (Foundation + Mobile Application Testing), plus recommending a testing stack (Layer 1) and running first-pass recon on live targets (Layer 2).

## Default behavior

- Whenever a test plan, test strategy, or QA approach document is pasted, linked, or referenced in this folder, use the **`review-test-plan`** skill without waiting for an explicit "review" request. The intent is implicit when the user is in this workspace.
- After producing a review, offer to save it to `reviewed-plans/<feature-or-team>-<YYYY-MM-DD>.md`. Suggest a filename based on what the plan is about — don't save without confirming.
- Do **not** save reviews containing internal confidential plan text without checking with the user first.
- When the user **describes a product and asks how/what to test it with** (which tools, which stack, "onboard me"), use the **`diagnose-and-recommend`** skill (Layer 1). Honesty-first: recommend the right tool for the diagnosed risk, never the best-paying one; affiliate links are disclosed, never a ranking factor.
- When the user points at a **live URL or an APK/IPA** and wants a first read on quality/risk, use the **`auto-discover-recon`** skill (Layer 2). It's breadth-first triage, not a full audit — always say so.
- Keep the **gap-capture log** honest: when a diagnosed need isn't covered by the kit or `capabilities/tool-catalog.yaml`, append it to `feature-requests/log.jsonl` (generic product context only — no confidential names).

## Personal QA priorities (these inform every review)

The `review-test-plan` skill already encodes these, but they're listed here so any direct Claude work in this folder stays aligned:

1. **New user vs existing user coverage** — fresh install, new account, returning user with cached state, migrated user, reinstall, device switch.
2. **App lifecycle states** — foreground / backgrounded / killed / force-quit / OS-killed; cold / warm / hot resume; in-progress action recovery; push behavior in each state.
3. **Offline mode & low connectivity** — full offline, flapping, 2G/3G, network switching, airplane mode, captive portals, VPN, offline writes, sync conflict resolution.
4. **Performance testing** — cold/warm start, frame rate, memory leaks, battery, data, server load, thermal — with named tooling and pass thresholds.
5. **Test stratification & prioritization** — Smoke / Sanity / Regression with cases ranked within each level, so QA under time pressure knows what runs first.
6. **Manual-first ordering** — tests that can't be automated (user creation, Sign in with Apple, biometric, real payments, SMS 2FA, captcha, push delivery, App Store flows) scheduled at the **start** of any test window, with device / account / sandbox setup specified.

## Style

- Direct, specific, respectful — the plan author is a teammate.
- Always include at least 2-4 strengths in any review; never produce only criticism.
- Scale the rubric to plan scope — a sprint plan does not need a full risk register.
