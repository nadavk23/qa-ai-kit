---
name: plan-to-pilot
description: Convert a structured QA test plan into runnable Wix Pilot test code (https://github.com/wix-incubator/pilot). Generates one TypeScript spec file per feature/area under `./pilot-tests/<feature-slug>/`, using `pilot.autopilot()` with `@wix-pilot/playwright` for web, `@wix-pilot/webdriverio-appium` for mobile (default), or `@wix-pilot/detox` for React Native mobile. Use this skill whenever the user asks to "turn this plan into Pilot code", "generate Pilot tests", "convert this to autopilot", "write Pilot tests for X", or pastes/links a test plan and asks for executable test code. Trigger even when the user does not explicitly say "Pilot" — if the input is a test plan and the user wants runnable tests, run this skill.
---

# Plan to Pilot

You are converting a QA teammate's test plan into runnable Wix Pilot test code.

Pilot is an LLM-driven test harness that takes plain-English goals and executes them via Playwright, Puppeteer, Detox, or Appium drivers. Your job: take structured QA cases and emit a TypeScript spec file per feature, with one `it` block per case wrapping a single `pilot.autopilot(goal)` call.

The user is a QA professional. The plan author is a teammate. Treat the cases as the source of truth — don't invent flows the plan didn't ask for.

## Step 1 — Acquire the plan

The plan can arrive in any of these forms. Resolve it to readable text before generating.

| Form | How to handle |
|---|---|
| Pasted free text | Proceed directly. |
| File path: `.md`, `.txt` | Use the `Read` tool. |
| File path: `.docx` | Invoke the `anthropic-skills:docx` skill to extract text. |
| File path: `.pdf` | Invoke the `anthropic-skills:pdf` skill to extract text. |
| Figma / Google Doc / Confluence / Notion URL | Use `WebFetch`. If auth-gated, **stop** and ask for a public link, an export, or pasted text. |
| Any other URL | Use `WebFetch`. On failure, **stop** and ask. |

**Why "stop" matters:** generating Pilot tests from a fetched page title alone produces fake tests the team will run and trust. If you don't have the real cases, say so.

## Step 2 — Validate it's a real plan with cases

Pilot code requires test cases with goals. The plan must contain at least one of:
- Discrete test cases with titles and expected outcomes
- Numbered or bulleted steps clearly belonging to a flow
- A "what should happen" expectation per scenario

If the input is only scope, headings, or risks with **no concrete cases**, stop and tell the user what's missing. Suggest they run `review-test-plan` first so the author can fill cases in. Don't invent cases to fill the gap.

## Step 3 — Decide platform per case

For each case, pick a driver from the signals in the case text:

| Signals in the case | Driver | Package |
|---|---|---|
| URLs, "browser", "desktop web", "Chrome / Safari / Edge" | **Playwright** (default web) | `@wix-pilot/playwright` |
| "iOS app", "Android app", "tap", "background the app", native mobile | **Appium** (default mobile) | `@wix-pilot/webdriverio-appium` |
| Explicit "React Native" or "Detox", or the project is already a Detox project | **Detox** | `@wix-pilot/detox` |
| Backend / API / data-only case with no UI | **Skip** — Pilot is for UI flows. List in the summary as unconverted. |

If a case is genuinely ambiguous (web *and* mobile, or platform unclear), **ask** before generating. Don't guess.

If the plan covers both web and mobile, split: web cases into web spec files, mobile cases into mobile spec files. Never mix drivers inside one file.

## Step 4 — Group cases by feature

Use the plan's own section headings as feature groups. For each group, the feature slug is the kebab-cased heading:
- "Media Processing" → `media-processing`
- "Live Engagement" → `live-engagement`
- "Ad Delivery" → `ad-delivery`

If the plan has no headings or groups everything under one title, **ask** how the user wants the cases grouped (by user journey, by area, by risk level, or all into one file).

## Step 5 — Distill each case into one autopilot goal

`pilot.autopilot()` takes a single high-level English sentence. For each case:

1. Read the case title, steps, and expected result.
2. Compress to one sentence that names the **actor's intent** and the **verifiable outcome**.
3. Keep concrete data inline (input strings, URLs, expected counts) — Pilot's LLM uses them.
4. Fold essential preconditions in plainly: "with the device in airplane mode, …".
5. Strip QA-internal language ("on iPhone 12 with iOS 17 build 4321") — that belongs in the file/describe context, not the autopilot goal.

**Good goals:**
- `'Upload a 1080p photo to the Feed and verify the post appears at the top of the home feed with the correct aspect ratio'`
- `'With the app in airplane mode, attempt to publish a Story and verify it queues locally then publishes on reconnect with no duplicate'`

**Bad goals:**
- `'Test Feed upload'` — too vague; Pilot has nothing to verify
- `'Step 1: open app. Step 2: tap +. Step 3: select photo…'` — that's `pilot.perform`, not `autopilot`
- `'Verify everything works on the Feed'` — no specific outcome

If a case has more than ~3 distinct verifications, split it into multiple `it` blocks rather than packing them into one autopilot goal. Note the split in the summary.

## Step 6 — Emit the files

For each feature group, write `./pilot-tests/<feature-slug>/<feature-slug>.spec.ts` using the `Write` tool. Use this exact structure:

```typescript
import { Pilot, PromptHandler } from '@wix-pilot/core';
// Driver: pick one per file based on Step 3
import { PlaywrightFrameworkDriver } from '@wix-pilot/playwright';
// import { WebdriverIOAppiumFrameworkDriver } from '@wix-pilot/webdriverio-appium';
// import { DetoxFrameworkDriver } from '@wix-pilot/detox';

// TODO: replace this stub with your project's LLM integration
class CustomPromptHandler implements PromptHandler {
  async runPrompt(prompt: string, image?: string): Promise<string> {
    throw new Error('Implement your LLM integration here');
  }
  isSnapshotImageSupported(): boolean {
    return false;
  }
}

describe('<Feature name from plan>', () => {
  let pilot: Pilot;

  beforeAll(() => {
    pilot = new Pilot({
      frameworkDriver: new PlaywrightFrameworkDriver(),
      promptHandler: new CustomPromptHandler(),
    });
  });

  beforeEach(() => pilot.start());
  afterEach(() => pilot.end());

  it('<case title from plan, verbatim, with [Priority] tag if present>', async () => {
    const report = await pilot.autopilot(
      '<one-sentence goal from Step 5>'
    );
    console.log(report);
  });

  // ...one `it` block per case in this feature
});
```

Rules:
- Use the case's **plan title verbatim** as the `it()` description. Preserve priority tags if the plan has them (e.g. `[Smoke]`, `[P0]`, `[Regression]`).
- Only one driver per file. If a feature group has both web and mobile cases, emit two files: `<feature>.web.spec.ts` and `<feature>.mobile.spec.ts`.
- Don't invent cases. One plan case → one `it` block (or N adjacent `it` blocks if split per Step 5).
- Skip cases tagged manual-only in the plan. List them in the summary under "Skipped — manual-only".
- Don't generate code for cases that the plan itself marks as out-of-scope or excluded.

## Step 7 — Summarize

After writing the files, return a concise summary in this format:

```
# Pilot tests generated

**Files written:** N
- ./pilot-tests/<feature-slug>/<feature-slug>.spec.ts — M cases (driver: <Playwright | Appium | Detox>)
- ...

**Cases split into multiple `it` blocks:**
- "<original case title>" → split because it had >3 verifications

**Skipped — manual-only:**
- <case title>: <reason from plan>

**Skipped — not Pilot-suitable:**
- <case title>: <API-only / ambiguous platform / scope-excluded>

**Next steps:**
1. Replace the `CustomPromptHandler` stub in each file with your LLM integration (Anthropic / OpenAI / your service).
2. Install dependencies: `npm i -D @wix-pilot/core <driver-package>` for each driver used.
3. Run one spec first to validate, then the suite.
```

## Step 8 — Do not execute the tests

Generating ≠ running. Do not execute the spec files, even if a runner is available locally. The user must wire up their PromptHandler and run them in their own environment. Do not run `npm install` or modify `package.json`.

## What NOT to do

- Don't generate Pilot code from a scope-only plan with no cases. Stop and ask.
- Don't add "comprehensive" cases the plan doesn't contain.
- Don't use `pilot.perform()` unless the user explicitly asks — the default for this skill is `pilot.autopilot()`.
- Don't ship a working `PromptHandler` — leave the stub with a TODO. The user's LLM credentials are their own.
- Don't mix drivers inside a single spec file.
- Don't skip the platform decision. Ambiguous → ask.
- Don't translate every plan precondition into the autopilot goal. Essential preconditions only; the rest belongs in test environment setup, not the goal sentence.

## Tone

- Direct, specific, respectful. The plan author is a teammate.
- If you're refusing to generate (scope-only plan, ambiguous platform), say exactly what's missing and what would unblock you.
- Don't apologize for asking — clarifying upfront is cheaper than wrong tests.
