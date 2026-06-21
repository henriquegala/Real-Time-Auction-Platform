"""Standalone winner-worker service (Option A from redis_patterns.md).

Runs as its own container: `python -m app.realtime.winner`.

Loop:
  1. SELECT auctions where end_time <= now() AND winner_id IS NULL.
  2. For each, try `SET auction:{id}:closed 1 NX EX <lock_ttl>` — atomic claim.
     - NX guarantees only one worker (across N replicas) processes a given
       auction. The EX lets a crashed worker retry on the next pass.
  3. Read final state from Redis (fallback to SQL if cache cold).
  4. UPDATE auctions SET winner_id, closed_at = now().
  5. PUBLISH auction_closed on channel:auction:{id}.

Required schema (see NOTES_FOR_HENRIQUE.md in Phase 4):
  auctions.winner_id  INT NULL  REFERENCES users(id)
  auctions.closed_at  TIMESTAMPTZ NULL
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timezone
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .bids import channel_for
from .protocol import AuctionClosed

logger = logging.getLogger(__name__)

POLL_INTERVAL = float(os.environ.get("WINNER_POLL_INTERVAL", "2"))
LOCK_TTL_SECONDS = int(os.environ.get("WINNER_LOCK_TTL", "60"))


def _key(auction_id: int, suffix: str) -> str:
    return f"auction:{auction_id}:{suffix}"


async def _find_ended(session_factory: async_sessionmaker) -> list[int]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT id FROM auctions
                    WHERE end_time <= NOW() AT TIME ZONE 'UTC'
                      AND winner_id IS NULL
                      AND closed_at IS NULL
                    ORDER BY end_time ASC
                    LIMIT 200
                    """
                )
            )
        ).all()
    return [r.id for r in rows]


async def _final_state_from_redis(redis: Redis, auction_id: int) -> tuple[int | None, Decimal | None]:
    leader_b, current_b = await redis.mget(
        _key(auction_id, "leader"),
        _key(auction_id, "current"),
    )
    leader = leader_b.decode() if isinstance(leader_b, (bytes, bytearray)) else leader_b
    current = current_b.decode() if isinstance(current_b, (bytes, bytearray)) else current_b
    winner_id = int(leader) if leader else None
    amount = Decimal(current) if current and winner_id is not None else None
    return winner_id, amount


async def _final_state_from_db(
    session_factory: async_sessionmaker, auction_id: int
) -> tuple[int | None, Decimal | None]:
    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT user_id, amount FROM bids
                    WHERE auction_id = :aid
                    ORDER BY amount DESC, id DESC
                    LIMIT 1
                    """
                ),
                {"aid": auction_id},
            )
        ).first()
    if row is None:
        return None, None
    return row.user_id, Decimal(row.amount)


async def _persist_winner(
    session_factory: async_sessionmaker,
    *,
    auction_id: int,
    winner_id: int | None,
    closed_at: datetime,
) -> None:
    async with session_factory() as session:
        await session.execute(
            text(
                """
                UPDATE auctions
                SET winner_id = :wid, closed_at = :ts
                WHERE id = :aid AND closed_at IS NULL
                """
            ),
            {"wid": winner_id, "ts": closed_at, "aid": auction_id},
        )
        await session.commit()


async def claim_and_close(
    auction_id: int,
    redis: Redis,
    session_factory: async_sessionmaker,
) -> bool:
    """Attempt to atomically claim and finalize this auction.

    Returns True if this worker did the closing work, False if another worker
    held the lock or the lock could not be acquired.
    """
    got_lock = await redis.set(
        _key(auction_id, "closed"), "1", nx=True, ex=LOCK_TTL_SECONDS
    )
    if not got_lock:
        return False

    try:
        winner_id, amount = await _final_state_from_redis(redis, auction_id)
        if winner_id is None and amount is None:
            # Redis state cold (no one connected) — fall back to SQL.
            winner_id, amount = await _final_state_from_db(session_factory, auction_id)

        closed_at = datetime.now(timezone.utc)
        await _persist_winner(
            session_factory,
            auction_id=auction_id,
            winner_id=winner_id,
            closed_at=closed_at,
        )

        # Make the closed marker permanent (drop the TTL).
        await redis.set(_key(auction_id, "closed"), "1")

        event = AuctionClosed(
            auction_id=auction_id, winner_id=winner_id, winning_amount=amount
        )
        await redis.publish(
            channel_for(auction_id), json.dumps(event.model_dump(mode="json"))
        )
        logger.info(
            "closed auction %s winner=%s amount=%s", auction_id, winner_id, amount
        )
        return True
    except Exception:
        logger.exception("close failed for auction %s; lock will expire", auction_id)
        return False


async def run() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://auction:auction@db:5432/auction",
    )

    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = Redis.from_url(redis_url)

    stop = asyncio.Event()

    def _on_signal(*_: object) -> None:
        logger.info("winner-worker received stop signal")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            # Windows / restricted envs — fall back to default handling.
            pass

    logger.info(
        "winner-worker up: poll=%ss lock_ttl=%ss redis=%s",
        POLL_INTERVAL,
        LOCK_TTL_SECONDS,
        redis_url,
    )

    try:
        while not stop.is_set():
            try:
                ended = await _find_ended(session_factory)
                for aid in ended:
                    if stop.is_set():
                        break
                    await claim_and_close(aid, redis, session_factory)
            except Exception:
                logger.exception("winner loop iteration failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=POLL_INTERVAL)
            except asyncio.TimeoutError:
                pass
    finally:
        await redis.aclose()
        await engine.dispose()
        logger.info("winner-worker stopped")


if __name__ == "__main__":
    asyncio.run(run())
