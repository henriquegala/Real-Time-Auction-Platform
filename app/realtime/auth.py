"""JWT verification for WebSocket connections.

Token is passed via query string: ws://host/ws/auctions/{id}?token=<jwt>.
Reuses Henrique's JWT_SECRET env var (HS256).
"""
from __future__ import annotations

from fastapi import WebSocket

from .protocol import CloseCode


async def authenticate_ws(ws: WebSocket, secret: str) -> int | None:
    """Return the authenticated user_id, or None after closing the socket.

    Implemented in Phase 2.
    """
    raise NotImplementedError("Phase 2")
