from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ProgressHub:
    """Small in-process WebSocket fan-out for workflow state notifications."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[session_id].add(websocket)

    async def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._connections.get(session_id)
            if connections:
                connections.discard(websocket)
                if not connections:
                    self._connections.pop(session_id, None)

    async def publish(self, session_id: str, event: dict[str, Any]) -> None:
        """Broadcast state metadata; stale sockets are removed without blocking callers."""

        async with self._lock:
            targets = tuple(self._connections.get(session_id, ()))
        failed: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_json(event)
            except Exception:  # WebSocket disconnects are expected during navigation.
                failed.append(websocket)
        for websocket in failed:
            await self.disconnect(session_id, websocket)


progress_hub = ProgressHub()
