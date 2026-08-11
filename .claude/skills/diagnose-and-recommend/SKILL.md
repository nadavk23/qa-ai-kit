---
name: diagnose-and-recommend
description: The user describes their product in plain language (or points at what they're building) and this skill diagnoses its quality risks, then recommends which testing tools/MCPs to install — a Basic package by default plus Deep modules matched to the diagnosed risks, with honest disclosure of any affiliate/referral links. Missing capabilities are logged as feature-requests. Use this skill when the user asks "what should I use to test my product", "which tools do I need", "set me up for testing X", "recommend a QA stack", "onboard me", or describes a product and asks how to test it. This is Layer 1 (onboarding + recommendation). For pointing at a live URL/APK to get a first-pass map, use auto-discover-recon (Layer 2) instead.
---

# Diagnose & recommend (Layer 1)

The user describes their product; you diagnose its quality risks and recommend a
testing toolkit. Two rules define this skill's integrity — hold them absolutely:

1. **Honesty over payout.** Recommend the *right* tool for the diagnosed risk,
   never the best-paying one. Affiliate status is disclosed, never a ranking
   input. If the honest answer is "you don't need a paid tool yet," say that.
2. **Don't oversell coverage.** Diagnosis is reasoning from a description, not a
   test run. Say what you're inferring vs. what only running tests would confirm.

## Step 1 — Get the product picture

You need enough to diagnose. From the user's description, establish:

- **Platform(s):** web, iOS, Android, React Native, desktop, API/backend, or a mix.
- **Architecture signals:** SPA vs. server-rendered, native vs. hybrid, has a
  backend/API, real-time features, offline support, third-party SDKs.
- **Sensitive/high-risk surfaces:** accounts/auth, payments, PII/health data,
  user-generated content, push, background work, location.
- **Stage & scale:** prototype vs. production; expected load; team size / who runs QA.

If the description is too thin to diagnose, ask **one or two** targeted questions
(platform and the riskiest surface are usually enough) — don't dump a
questionnaire. If they instead pointed you at a **live URL or APK/IPA**, this is
the wrong skill for that part: run **`auto-discover-recon`** (Layer 2) first to
get real signal, then come back here to turn findings into a tool plan.

## Step 2 — Diagnose the risk profile

Map what you learned to a prioritized risk profile. Apply **both** lenses:

**A. The personal QA priorities** (from `CLAUDE.md` — the same judgment
`review-test-plan` encodes):
1. New vs. existing user (fresh install, migration, reinstall, device switch)
2. App lifecycle states (foreground/backgrounded/killed; cold/warm/hot resume)
3. Offline mode & low connectivity (flapping, 2G/3G, airplane, sync conflicts)
4. Performance (cold/warm start, frame rate, memory, battery, data, load)
5. Test stratification (smoke/sanity/regression, prioritized)
6. Manual-first ordering (unautomatable flows scheduled first)

**B. Product-type risk** — what this *kind* of product tends to break on
(payments → money-correctness + fraud edges; UGC → moderation + injection;
health → privacy + data integrity; real-time → sync + concurrency; etc.).

Produce a short ranked list: the top 3–6 risks, each tagged with the testing
**dimension** it lives in (functionality / UI / accessibility / performance /
security / compatibility / load). This ranking is what drives recommendations —
not the tool catalog's contents.

## Step 3 — Read the tool catalog

Read `capabilities/tool-catalog.yaml`. It's the knowledge base: each tool has
`covers`, `when_right`, `not_for`, `tier`, `install`, and an `affiliate` field.

**Selection rule:** match tools to the *diagnosed risks* via `covers` +
`when_right`. Never select or rank on `affiliate`. If nothing in the catalog fits
a real diagnosed risk, that's a **gap** → Step 5.

## Step 4 — Build the recommendation

Structure the output as **Basic package + Deep modules**, so the user isn't
buried in tools they don't need yet.

- **Basic package (always):** the `tier: basic` tools relevant to their
  platform(s) — the kit's own `qa-execution`, plus free/open helpers (axe-core,
  Lighthouse) where the platform matches. This is the "install these now" set.
- **Deep modules (on-demand):** `tier: deep` tools, but **only** those a
  diagnosed Step-2 risk actually warrants. For each, name the *risk it addresses*
  so the user sees why. Don't list all deep tools — list the earned ones.
- **Device clouds / affiliate tools:** recommend a real-device cloud **only**
  when the diagnosed risk is real-device / wide-matrix fragmentation, and always:
  (a) tell them to try the kit's local drivers first, (b) offer more than one
  option, (c) **disclose the affiliate relationship** using the `disclosure`
  text from the catalog. If they don't need it, say so plainly.

For each recommended tool give: name, the risk/dimension it covers, the one-line
install, and (if affiliate) the disclosure. Keep it scannable.

## Step 5 — Capture gaps as feature-requests

If a diagnosed risk has **no good fit** in the catalog or the kit, append a line
to `feature-requests/log.jsonl` (see `feature-requests/README.md` for the
schema). Use the current date from your context, keep `product_context` generic
(no confidential names), and pick a `candidate_tier`
(basic/deep/**enterprise** — enterprise = the paid-tier signal). Tell the user
you logged it. This is how the roadmap and paid tier get their signal — don't
skip it, and don't invent a tool to paper over the gap.

## Step 6 — Output format

```
# Testing setup for <product, in your own words>

## Diagnosed risk profile
1. <risk> — <dimension> — <one line why it matters for this product>
2. ...

## Basic package (install now)
- <tool> — covers <dimension> — `<install>`
- ...

## Deep modules (add when you tackle these risks)
- <tool> — for <the specific risk> — `<install>`
- ...

## Real-device / cross-browser (only if you need it)
- <cloud option A> / <option B> — for <matrix risk>
  Disclosure: <affiliate disclosure text, verbatim from catalog, if applicable>
  Try the kit's local drivers first — only pay for this if the matrix is the gap.

## Gaps I logged (not covered by the kit yet)
- <capability> → logged to feature-requests as <requested_module> (<tier>)

## Honest caveats
- This is a diagnosis from your description, not a test run. Point me at a live
  URL/APK with `auto-discover-recon` to confirm with real signal.
```

## What NOT to do

- Don't rank or steer by affiliate payout. Ever. It's disclosure-only.
- Don't recommend a paid device cloud when local drivers cover the need.
- Don't list every deep/enterprise tool — only the ones a diagnosed risk earns.
- Don't invent a catalog entry or a capability to avoid logging a gap.
- Don't present diagnosis as verified coverage — it's inference until tests run.
- Don't write confidential product details into the feature-requests log.

## Tone

- Direct, specific, respectful — you're equipping a fellow QA, not upselling.
- Lead with the risk, then the tool. The user should understand *why* before *what*.
- When the honest answer is "you're fine with the free/basic set," say it and stop.
