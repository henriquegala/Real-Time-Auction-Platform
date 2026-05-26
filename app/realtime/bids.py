"""Bid handler: atomic Lua call -> SQL persist -> Redis publish.

Order is mandatory:
  1. EVALSHA bid.lua  (atomic check-and-set in Redis)
  2. INSERT into bids table via Henrique's session factory
  3. PUBLISH to channel:auction:{id}   <-- fanout to all workers
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi import WebSocket

LUA_PATH = Path(__file__).parent / "lua" / "bid.lua"


async def load_bid_script(redis) -> str:
    """SCRIPT LOAD bid.lua at startup, return the sha. (Phase 2)"""
    raise NotImplementedError("Phase 2")


async def warm_cache(auction_id: int, db, redis) -> None:
    """Populate auction:{id}:current/leader/ends_at from SQL on first connect. (Phase 2)"""
    raise NotImplementedError("Phase 2")


async def handle_place_bid(
    *,
    auction_id: int,
    user_id: int,
    amount: Decimal,
    ws: WebSocket,
    state,
) -> None:
    """Validate ownership, call Lua, persist, publish. (Phase 2)"""
    raise NotImplementedError("Phase 2")


async def pubsub_loop(app) -> None:
    """Subscribe to channel:auction:* and fan out to local rooms. (Phase 2)"""
    raise NotImplementedError("Phase 2")
