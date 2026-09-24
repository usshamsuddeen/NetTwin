"""WebSocketHub: fan-out with per-client queues and drop-on-slow backpressure."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


class WebSocketHub:
    def __init__(self) -> None:
        self._clients: dict[WebSocket, asyncio.Queue[str]] = {}

    async def connect(self, ws: WebSocket, snapshot: dict[str, Any]) -> None:
        await ws.accept()
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=8)
        self._clients[ws] = queue
        await ws.send_text(json.dumps(snapshot))
        task = asyncio.create_task(self._sender(ws, queue))
        try:
            while True:
                await ws.receive_text()  # keepalive / ignore client input
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            task.cancel()
            self._clients.pop(ws, None)

    async def _sender(self, ws: WebSocket, queue: asyncio.Queue[str]) -> None:
        try:
            while True:
                msg = await queue.get()
                await ws.send_text(msg)
        except Exception:
            pass

    async def broadcast(self, message: dict[str, Any]) -> None:
        if not self._clients:
            return
        payload = json.dumps(message)
        for queue in self._clients.values():
            if queue.full():
                try:
                    queue.get_nowait()  # drop oldest for slow clients
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    @property
    def client_count(self) -> int:
        return len(self._clients)
