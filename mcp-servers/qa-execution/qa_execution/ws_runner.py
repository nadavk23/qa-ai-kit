"""WebSocket client pooling and state management."""

import asyncio
import json
from typing import Any, Optional


class WebSocketClient:
    """Wraps a websockets connection with send/recv abstractions."""

    def __init__(self, url: str, headers: Optional[dict[str, str]] = None):
        self.url = url
        self.headers = headers or {}
        self.client = None  # websockets.WebSocketClientProtocol
        self.recv_buffer = []  # buffered incoming messages

    async def connect(self) -> None:
        """Connect to WebSocket server."""
        try:
            import websockets
        except ImportError:
            raise RuntimeError(
                "websockets not installed. Install it with: pip install websockets"
            )

        self.client = await websockets.connect(
            self.url,
            extra_headers=self.headers if self.headers else None,
            ping_interval=20,
            ping_timeout=10,
        )

    async def send(self, message: str) -> None:
        """Send a message through the WebSocket."""
        if not self.client:
            raise RuntimeError("WebSocket not connected. Call connect() first.")
        await self.client.send(message)

    async def recv(self, timeout: float = 5.0) -> str:
        """Receive a message from the WebSocket with optional timeout."""
        if not self.client:
            raise RuntimeError("WebSocket not connected. Call connect() first.")

        try:
            msg = await asyncio.wait_for(self.client.recv(), timeout=timeout)
            return msg
        except asyncio.TimeoutError:
            raise TimeoutError(f"WebSocket recv timeout after {timeout}s")

    async def recv_until(
        self, predicate: callable, timeout: float = 10.0
    ) -> str:
        """Receive messages until predicate(message) returns True."""
        if not self.client:
            raise RuntimeError("WebSocket not connected. Call connect() first.")

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError(
                    f"WebSocket recv_until timeout after {timeout}s"
                )

            try:
                msg = await asyncio.wait_for(
                    self.client.recv(), timeout=remaining
                )
                if predicate(msg):
                    return msg
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"WebSocket recv_until timeout after {timeout}s"
                )

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self.client:
            await self.client.close()
            self.client = None
