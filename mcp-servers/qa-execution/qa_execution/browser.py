import asyncio
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)


class BrowserSession:
    """Single Playwright browser instance shared across MCP tool calls.

    Lazy-started on first use. Captures console + network events while alive
    so the `web_logs` tool can read them.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._storage_state: str | None = None
        self.console_log: list[dict[str, Any]] = []
        self.network_log: list[dict[str, Any]] = []

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser not started — call ensure_started() first.")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Browser not started.")
        return self._context

    async def ensure_started(self) -> None:
        async with self._lock:
            if self._page is not None:
                return
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            ctx_kwargs: dict[str, Any] = {}
            if self._storage_state:
                ctx_kwargs["storage_state"] = self._storage_state
            self._context = await self._browser.new_context(**ctx_kwargs)
            self._page = await self._context.new_page()
            self._wire_logging(self._page)

    async def restart_with_storage(self, storage_state: str) -> None:
        async with self._lock:
            self._storage_state = storage_state
            if self._context:
                await self._context.close()
            if self._browser is None:
                # Browser hasn't started yet; storage will be applied on first start.
                return
            self._context = await self._browser.new_context(storage_state=storage_state)
            self._page = await self._context.new_page()
            self._wire_logging(self._page)
            self.console_log.clear()
            self.network_log.clear()

    async def shutdown(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def _wire_logging(self, page: Page) -> None:
        page.on(
            "console",
            lambda msg: self.console_log.append({"type": msg.type, "text": msg.text}),
        )
        page.on(
            "response",
            lambda resp: self.network_log.append(
                {"status": resp.status, "method": resp.request.method, "url": resp.url}
            ),
        )
