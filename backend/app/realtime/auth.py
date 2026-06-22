"""JWT verification for WebSocket connections.

Token is passed via query string: ws://host/ws/auctions/{id}?token=<jwt>.
Reuses the same HS256 secret Henrique's /api/auth/login signs with. The token
payload is {"sub": <username>, "user_id": <int>}, so the numeric id lives in the
`user_id` claim (the `sub` claim holds the username).
"""
from __future__ import annotations

import jwt
from fastapi import WebSocket

from .protocol import CloseCode


async def authenticate_ws(ws: WebSocket, secret: str) -> int | None:
    """Verify the `token` query param. On failure close with 4401 and return None.

    On success returns the integer user_id from the JWT `user_id` claim.
    """
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=CloseCode.AUTH_FAILED)
        return None
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return int(payload["user_id"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        await ws.close(code=CloseCode.AUTH_FAILED)
        return None
