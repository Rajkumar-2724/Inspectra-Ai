"""Tiny WebSocket broadcaster; publish() is safe to call from worker threads."""
import asyncio
import json

from fastapi import WebSocket


class EventHub:
    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket):
        self.loop = asyncio.get_running_loop()
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket):
        self.clients.discard(ws)

    async def _broadcast(self, text: str):
        for ws in list(self.clients):
            try:
                await ws.send_text(text)
            except Exception:  # noqa: BLE001
                self.clients.discard(ws)

    def publish(self, event: dict):
        if not self.clients or self.loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._broadcast(json.dumps(event)), self.loop)
        except Exception:  # noqa: BLE001
            pass


hub = EventHub()
