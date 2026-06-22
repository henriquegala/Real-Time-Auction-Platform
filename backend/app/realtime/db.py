"""Small DB helpers shared by routes/bids/winner.

These funnel through Henrique's session factory, looked up dynamically from
`app.state.db_session_factory` (set during lifespan startup). The realtime
module uses raw SQL via SQLAlchemy `text()` so it does not hard-couple to
Henrique's ORM class names — only the table/column names listed in
NOTES_FOR_HENRIQUE.md (Phase 4).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


@dataclass(slots=True)
class AuctionRow:
    id: int
    item: str
    owner_id: int
    start_price: Decimal
    end_time: datetime
    current_bid: Decimal
    leader_user_id: int | None


async def fetch_auction(session_factory: async_sessionmaker, auction_id: int) -> AuctionRow | None:
    """Read auction + current leader/highest bid in one transaction.

    Maps Henrique's schema onto the realtime layer's vocabulary:
      auctions(id, title->item, creator_id->owner_id, starting_price->start_price, end_time)
      bids(id, auction_id, bidder_id->user_id, amount, created_at)
    """
    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT a.id, a.title AS item, a.creator_id AS owner_id,
                           a.starting_price AS start_price, a.end_time,
                           COALESCE(b.amount, a.starting_price) AS current_bid,
                           b.bidder_id AS leader_user_id
                    FROM auctions a
                    LEFT JOIN LATERAL (
                        SELECT amount, bidder_id
                        FROM bids
                        WHERE auction_id = a.id
                        ORDER BY amount DESC, id DESC
                        LIMIT 1
                    ) b ON true
                    WHERE a.id = :aid
                    """
                ),
                {"aid": auction_id},
            )
        ).first()
    if row is None:
        return None
    return AuctionRow(
        id=row.id,
        item=row.item,
        owner_id=row.owner_id,
        start_price=Decimal(row.start_price),
        end_time=row.end_time,
        current_bid=Decimal(row.current_bid),
        leader_user_id=row.leader_user_id,
    )


async def insert_bid(
    session_factory: async_sessionmaker,
    *,
    auction_id: int,
    user_id: int,
    amount: Decimal,
    created_at: datetime,
) -> None:
    async with session_factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO bids (auction_id, bidder_id, amount, created_at)
                VALUES (:aid, :uid, :amt, :ts)
                """
            ),
            {"aid": auction_id, "uid": user_id, "amt": amount, "ts": created_at},
        )
        await session.commit()


async def fetch_username(session_factory: async_sessionmaker, user_id: int) -> str:
    async with session_factory() as session:
        row = (
            await session.execute(
                text("SELECT username FROM users WHERE id = :uid"),
                {"uid": user_id},
            )
        ).first()
    return row.username if row is not None else f"user_{user_id}"
