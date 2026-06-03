import { Pilot, PromptHandler } from '@wix-pilot/core';
import { WebdriverIOAppiumFrameworkDriver } from '@wix-pilot/webdriverio-appium';

// TODO: replace this stub with your project's LLM integration (Anthropic / OpenAI / internal service).
class CustomPromptHandler implements PromptHandler {
  async runPrompt(prompt: string, image?: string): Promise<string> {
    throw new Error('Implement your LLM integration here');
  }
  isSnapshotImageSupported(): boolean {
    return false;
  }
}

// Runtime prerequisites for this spec (set up before run, do not commit credentials):
//   - A seeded Google test account (email + password) reachable from the iOS simulator/device.
//   - Appium server running with the target app installed.
//   - The OAuth flow opens in ASWebAuthenticationSession; Appium must be configured to interact
//     with the system sheet (set autoAcceptAlerts / use mobile: activateApp transitions as needed).
//   - Google may present "verify it's you" challenges on first login from a new device; pre-authorize
//     the test account from this device once, manually, before relying on this spec in CI.

describe('Sign in with Google (iOS)', () => {
  let pilot: Pilot;

  beforeAll(() => {
    pilot = new Pilot({
      frameworkDriver: new WebdriverIOAppiumFrameworkDriver(),
      promptHandler: new CustomPromptHandler(),
    });
  });

  beforeEach(() => pilot.start());
  afterEach(() => pilot.end());

  it("User signs in with Google and lands on the home screen [Smoke]", async () => {
    const report = await pilot.autopilot(
      "Tap the 'Sign in with Google' button on the login screen, complete Google authentication with the seeded test account, and verify the app navigates to the post-login home screen showing the signed-in user's profile."
    );
    console.log(report);
  });
});
