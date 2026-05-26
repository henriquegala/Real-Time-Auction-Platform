"""Per-auction WebSocket connection manager.

One instance lives on app.state.ws_manager. Handles only the *local*
(in-process) fanout. Cross-worker fanout goes through Redis Pub/Sub
(see bids.py / main.py lifespan).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, ws: WebSocket, auction_id: int) -> None:
        raise NotImplementedError("Phase 2")

    def disconnect(self, ws: WebSocket, auction_id: int) -> None:
        raise NotImplementedError("Phase 2")

    async def send_to_room(self, auction_id: int, message: dict[str, Any]) -> None:
        raise NotImplementedError("Phase 2")
