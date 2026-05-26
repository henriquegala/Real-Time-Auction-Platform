"""Standalone winner-worker service (Option A from redis_patterns.md).

Runs as its own container: `python -m app.realtime.winner`.
Loop:
  - find auctions with end_time <= now() AND winner_id IS NULL
  - claim atomically with SET auction:{id}:closed 1 NX
  - on success: read final state, write winner_id to SQL, publish auction_closed
"""
from __future__ import annotations

import asyncio


async def claim_and_close(auction_id: int, redis, db) -> bool:
    """Try to atomically claim closing the auction. (Phase 3)"""
    raise NotImplementedError("Phase 3")


async def run() -> None:
    """Main worker loop. (Phase 3)"""
    raise NotImplementedError("Phase 3")


if __name__ == "__main__":
    asyncio.run(run())
