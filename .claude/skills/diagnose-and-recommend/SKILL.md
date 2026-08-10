---
name: diagnose-and-recommend
description: PLACEHOLDER (Layer 1 — not yet built). Intended: the user describes their product in plain language, and the kit diagnoses its quality risks and recommends which tools/MCPs to install (e.g. Appium for mobile, k6 for load), splitting a Basic package from deeper on-demand modules, and logs missing capabilities as feature-requests. Until built, use this skill only to explain what Layer 1 will do and to route the user to what exists today. Do NOT fabricate a recommendation engine.
---

# Diagnose & recommend (Layer 1) — PLACEHOLDER

**Status: not implemented.** This skill is a signpost, not a capability yet.
The execution engine (qa-execution) and Layer 2 (auto-discovery recon) are built;
Layer 1 is scoped but not written.

## What Layer 1 will do (when built)

1. **Diagnose from a description.** User describes their product in plain
   language ("a React Native fitness app with a social feed and Stripe payments").
   The skill classifies platform(s) and architecture and maps them to a risk
   profile using the personal QA priorities in `CLAUDE.md` (new-vs-existing user,
   lifecycle states, offline/connectivity, performance, manual-first flows) —
   the same judgment `review-test-plan` applies to plans, pointed at a product.
2. **Recommend tools/MCPs.** Output a ranked install set split into a **Basic
   package by default** and **deeper modules on demand** (e.g. Appium for mobile,
   k6 for load/stress, the kit's own qa-execution for web/API/iOS/Android, and —
   honestly disclosed — third-party device clouds like BrowserStack/LambdaTest
   where genuinely appropriate).
3. **Honesty-first routing.** Recommendations key off diagnosed risk, never off
   referral payout. Affiliate status is a separate, visible field — disclosed,
   never a ranking input.
4. **Gap-capture.** When a needed capability isn't covered, append a structured
   entry to a feature-request log — the seed of the roadmap and enterprise tier.

## What to do until it's built

If a user triggers this skill today:

- **Explain** that Layer 1 is on the roadmap and what it will do (above).
- **Route to what exists:**
  - Live URL or running app and they want a first read → **`auto-discover-recon`**
    (Layer 2, built).
  - A written test plan to critique → **`review-test-plan`**.
  - A bug to file → **`write-bug-report`**.
  - Runnable Pilot specs from a plan → **`plan-to-pilot`**.
- **Do not** invent a tool catalog, risk score, or install recommendation as if
  the engine existed. If the user wants a manual recommendation, give it as your
  own reasoning and say plainly it's hand-done, not the (future) engine.

## Build notes (for whoever implements this)

- Ship as a **skill + a `capabilities/tool-catalog.yaml` data file**, not a new
  MCP server — Layer 1 is diagnosis + reasoning, no new execution primitives.
- The tool-catalog entry shape should carry: name, purpose, when-it's-the-right-
  call, install command, and a nullable `affiliate` field kept separate from
  ranking.
- Gap-capture: append-only JSONL/markdown under `feature-requests/`, local for
  v1; route through the future MCP Gateway later.
- Wire a trigger note into `CLAUDE.md` so describing a product in this workspace
  invokes this skill, mirroring how pasting a plan invokes `review-test-plan`.
