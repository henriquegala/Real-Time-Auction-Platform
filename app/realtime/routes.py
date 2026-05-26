"""WebSocket endpoint for live auctions.

URL: ws://host:8000/ws/auctions/{auction_id}?token=<jwt>

Lifecycle:
  1. authenticate_ws() — closes 4401 on bad/missing token
  2. owner check vs. auction.owner_id — closes 4403 on self-bid attempt
  3. warm Redis cache from SQL on first connect
  4. send AuctionState
  5. loop:
       - receive_json with idle timeout (4408 after 60s)
       - dispatch place_bid -> handle_place_bid, ping -> pong
"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .auth import authenticate_ws
from .protocol import CloseCode

router = APIRouter()


@router.websocket("/ws/auctions/{auction_id}")
async def auction_socket(ws: WebSocket, auction_id: int) -> None:
    """Live bidding socket. Full implementation in Phase 2."""
    # Phase 2 wiring outline (do not remove — used as the impl checklist):
    #
    #   user_id = await authenticate_ws(ws, ws.app.state.jwt_secret)
    #   if user_id is None:
    #       return
    #   mgr = ws.app.state.ws_manager
    #   await mgr.connect(ws, auction_id)
    #   try:
    #       await warm_cache(auction_id, ..., ws.app.state.redis)
    #       state = await load_auction_state(auction_id, ws.app.state)
    #       await ws.send_json(state.model_dump(mode="json"))
    #       while True:
    #           try:
    #               raw = await asyncio.wait_for(ws.receive_json(), timeout=60)
    #           except asyncio.TimeoutError:
    #               await ws.close(code=CloseCode.IDLE_TIMEOUT)
    #               return
    #           msg = ClientMessageAdapter.validate_python(raw)
    #           if isinstance(msg, PlaceBid):
    #               await handle_place_bid(...)
    #           elif isinstance(msg, Ping):
    #               await ws.send_json(Pong().model_dump())
    #   except WebSocketDisconnect:
    #       pass
    #   finally:
    #       mgr.disconnect(ws, auction_id)
    raise NotImplementedError("Phase 2")
