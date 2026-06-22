"""WebSocket endpoint for live auctions.

URL: ws://host:8000/ws/auctions/{auction_id}?token=<jwt>

Lifecycle:
  1. authenticate_ws()                 — close 4401 on bad/missing token
  2. fetch auction from DB             — close 4404 if missing
  3. warm Redis cache (idempotent)
  4. accept + register in room
  5. send AuctionState
  6. loop: receive_json with 60s idle  — close 4408 on timeout
       - place_bid -> handle_place_bid
       - ping      -> pong
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from .auth import authenticate_ws
from .bids import handle_place_bid, warm_cache
from .db import fetch_auction
from .protocol import (
    AuctionState,
    BidRejected,
    ClientMessageAdapter,
    CloseCode,
    PlaceBid,
    Ping,
    Pong,
)

logger = logging.getLogger(__name__)

IDLE_TIMEOUT_SECONDS = 60.0

router = APIRouter()


@router.websocket("/ws/auctions/{auction_id}")
async def auction_socket(ws: WebSocket, auction_id: int) -> None:
    state = ws.app.state

    user_id = await authenticate_ws(ws, state.jwt_secret)
    if user_id is None:
        return

    auction = await fetch_auction(state.db_session_factory, auction_id)
    if auction is None:
        await ws.close(code=CloseCode.NOT_FOUND)
        return

    await warm_cache(auction_id, auction, state.redis)

    mgr = state.ws_manager
    await mgr.connect(ws, auction_id)
    try:
        initial = AuctionState(
            auction_id=auction.id,
            item=auction.item,
            current_bid=auction.current_bid,
            leader_user_id=auction.leader_user_id,
            ends_at=auction.end_time,
            owner_id=auction.owner_id,
        )
        await ws.send_json(initial.model_dump(mode="json"))

        while True:
            try:
                raw = await asyncio.wait_for(
                    ws.receive_json(), timeout=IDLE_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                await ws.close(code=CloseCode.IDLE_TIMEOUT)
                return

            try:
                msg = ClientMessageAdapter.validate_python(raw)
            except ValidationError:
                await ws.send_json(BidRejected(reason="too_low").model_dump())
                continue

            if isinstance(msg, PlaceBid):
                await handle_place_bid(
                    auction_id=auction_id,
                    user_id=user_id,
                    owner_id=auction.owner_id,
                    amount=msg.amount,
                    ws=ws,
                )
            elif isinstance(msg, Ping):
                await ws.send_json(Pong().model_dump())
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws handler crashed for auction %s user %s", auction_id, user_id)
        try:
            await ws.close(code=CloseCode.NORMAL)
        except Exception:
            pass
    finally:
        mgr.disconnect(ws, auction_id)
