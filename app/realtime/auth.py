"""JWT verification for WebSocket connections.

Token is passed via query string: ws://host/ws/auctions/{id}?token=<jwt>.
Reuses Henrique's JWT_SECRET env var (HS256, `sub` carries the user id).
"""
from __future__ import annotations

import jwt
from fastapi import WebSocket

from .protocol import CloseCode


async def authenticate_ws(ws: WebSocket, secret: str) -> int | None:
    """Verify the `token` query param. On failure close with 4401 and return None.

    On success returns the integer user_id from the JWT `sub` claim.
    """
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=CloseCode.AUTH_FAILED)
        return None
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        await ws.close(code=CloseCode.AUTH_FAILED)
        return None
