"""Record-flow: Auto-generate YAML tests from user interactions."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class RecordedEvent:
    """A single recorded user interaction."""
    type: str  # 'click' | 'input' | 'key' | 'navigate' | 'scroll'
    selector: Optional[str] = None
    text: Optional[str] = None
    key: Optional[str] = None
    url: Optional[str] = None
    direction: Optional[str] = None
    timestamp: float = 0.0


class WebRecorder:
    """Records web interactions and generates YAML tests."""

    INJECT_SCRIPT = """
    (() => {
        window.__argusRecorder = {
            events: [],
            lastUrl: window.location.href,
            currentSelector: null,

            findBestSelector(el) {
                if (!el || el.nodeType !== 1) return null;

                // Try data-testid first
                if (el.getAttribute('data-testid')) {
                    return `[data-testid="${el.getAttribute('data-testid')}"]`;
                }

                // Try aria-label
                if (el.getAttribute('aria-label')) {
                    return `[aria-label="${el.getAttribute('aria-label')}"]`;
                }

                // Try id
                if (el.id) return `#${el.id}`;

                // Build CSS path
                const path = [];
                let current = el;
                while (current && current.nodeType === 1 && current !== document.body) {
                    let selector = current.tagName.toLowerCase();
                    if (current.id) selector += `#${current.id}`;
                    else if (current.className) {
                        const classes = current.className.split(' ').filter(c => !c.startsWith('__')).join('.');
                        if (classes) selector += `.${classes}`;
                    }
                    path.unshift(selector);
                    current = current.parentElement;
                }
                return path.join(' > ');
            },

            recordClick(el) {
                const selector = this.findBestSelector(el);
                const text = el.textContent?.trim().substring(0, 50);
                this.events.push({
                    type: 'click',
                    selector,
                    text,
                    timestamp: Date.now()
                });
            },

            recordInput(el) {
                const selector = this.findBestSelector(el);
                this.events.push({
                    type: 'input',
                    selector,
                    text: el.value || '',
                    timestamp: Date.now()
                });
            },

            recordKey(key) {
                this.events.push({
                    type: 'key',
                    key,
                    timestamp: Date.now()
                });
            },

            recordNavigate(url) {
                if (url !== this.lastUrl) {
                    this.events.push({
                        type: 'navigate',
                        url,
                        timestamp: Date.now()
                    });
                    this.lastUrl = url;
                }
            }
        };

        // Listen for clicks
        document.addEventListener('click', (e) => {
            if (!e.target.closest('[data-argus-ignore]')) {
                window.__argusRecorder.recordClick(e.target);
            }
        }, true);

        // Listen for input changes (debounce)
        let inputTimeout;
        document.addEventListener('input', (e) => {
            clearTimeout(inputTimeout);
            inputTimeout = setTimeout(() => {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                    window.__argusRecorder.recordInput(e.target);
                }
            }, 300);
        }, true);

        // Listen for key presses
        document.addEventListener('keydown', (e) => {
            if (['Enter', 'Tab', 'Escape', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
                window.__argusRecorder.recordKey(e.key);
            }
        }, true);

        // Listen for navigation
        const originalPushState = window.history.pushState;
        window.history.pushState = function(...args) {
            originalPushState.apply(window.history, args);
            window.__argusRecorder.recordNavigate(window.location.href);
        };

        window.addEventListener('popstate', () => {
            window.__argusRecorder.recordNavigate(window.location.href);
        });
    })();
    """

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.events = []
        self.browser = None
        self.page = None

    async def start_recording(self, headless: bool = False):
        """Start browser and inject recording script."""
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)
        self.page = await self.browser.new_page()

        await self.page.goto(self.base_url)
        await self.page.evaluate(self.INJECT_SCRIPT)

        print(f"🎬 Recording started at {self.base_url}")
        print("⏸️  Press ENTER in the terminal when done...")

    async def get_events(self) -> list[RecordedEvent]:
        """Fetch recorded events from the page."""
        if not self.page:
            raise RuntimeError("Recording not started. Call start_recording() first.")

        raw_events = await self.page.evaluate("window.__argusRecorder.events || []")

        events = []
        for raw in raw_events:
            event = RecordedEvent(
                type=raw.get("type"),
                selector=raw.get("selector"),
                text=raw.get("text"),
                key=raw.get("key"),
                url=raw.get("url"),
                direction=raw.get("direction"),
                timestamp=raw.get("timestamp", 0)
            )
            events.append(event)

        return events

    async def stop_recording(self) -> list[RecordedEvent]:
        """Stop recording and return all events."""
        events = await self.get_events()
        await self.browser.close()
        await self.playwright.stop()
        return events

    @staticmethod
    def events_to_yaml(events: list[RecordedEvent], name: str = "Recorded test") -> str:
        """Convert recorded events to YAML test format."""
        lines = [
            f"name: {name}",
            "---",
        ]

        for i, event in enumerate(events):
            if event.type == "click":
                if event.selector:
                    lines.append(f"- action: click")
                    lines.append(f"  selector: \"{event.selector}\"")
                elif event.text:
                    lines.append(f"- action: click")
                    lines.append(f"  text: \"{event.text}\"")

            elif event.type == "input":
                if event.selector and event.text:
                    lines.append(f"- action: type")
                    lines.append(f"  selector: \"{event.selector}\"")
                    # Escape quotes in text
                    escaped_text = event.text.replace('"', '\\"')
                    lines.append(f"  text: \"{escaped_text}\"")

            elif event.type == "key":
                if event.key in ["Enter", "Tab", "Escape"]:
                    lines.append(f"- action: press")
                    lines.append(f"  key: {event.key}")

            elif event.type == "navigate":
                lines.append(f"- action: navigate")
                lines.append(f"  url: \"{event.url}\"")

        # Add final assertion
        lines.extend([
            "- action: screenshot",
            "  path: artifacts/recorded.png"
        ])

        return "\n".join(lines)

    @staticmethod
    def save_yaml(yaml_content: str, output_path: str) -> Path:
        """Save YAML test to file."""
        output = Path(output_path).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(yaml_content)
        return output


async def record_flow_cli(base_url: str, output_path: str, headless: bool = False) -> str:
    """CLI entry point for record-flow."""
    recorder = WebRecorder(base_url)
    await recorder.start_recording(headless=headless)

    # Wait for ENTER in terminal
    try:
        await asyncio.get_event_loop().run_in_executor(None, input)
    except KeyboardInterrupt:
        pass

    events = await recorder.stop_recording()
    yaml_content = WebRecorder.events_to_yaml(events, name=Path(output_path).stem)
    output = WebRecorder.save_yaml(yaml_content, output_path)

    return f"✅ Generated: {output}\n📝 {len(events)} interactions recorded"
