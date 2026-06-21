"""Per-auction WebSocket connection manager.

One instance lives on app.state.ws_manager. Handles only the *local*
(in-process) fanout. Cross-worker fanout goes through Redis Pub/Sub
(see bids.pubsub_loop).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, ws: WebSocket, auction_id: int) -> None:
        await ws.accept()
        self.rooms[auction_id].add(ws)

    def disconnect(self, ws: WebSocket, auction_id: int) -> None:
        room = self.rooms.get(auction_id)
        if room is None:
            return
        room.discard(ws)
        if not room:
            self.rooms.pop(auction_id, None)

    async def send_to_room(self, auction_id: int, message: dict[str, Any]) -> None:
        room = self.rooms.get(auction_id)
        if not room:
            return
        dead: list[WebSocket] = []
        for ws in room:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, auction_id)
