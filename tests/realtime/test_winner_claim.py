"""Tests for the winner-worker's atomic claim primitive.

Only the Redis-level mutex is exercised here (no DB). The full
`claim_and_close` path is exercised in the integration test once the
SQL schema lands.
"""
from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.asyncio


async def test_set_nx_claim_only_succeeds_once(redis_client, auction_id):
    """SET ... NX is the primitive `claim_and_close` uses to dedupe workers."""
    key = f"auction:{auction_id}:closed"

    first = await redis_client.set(key, "1", nx=True, ex=60)
    second = await redis_client.set(key, "1", nx=True, ex=60)
    third = await redis_client.set(key, "1", nx=True, ex=60)

    assert first is True
    assert second is None or second is False
    assert third is None or third is False


async def test_set_nx_under_concurrency(redis_client, auction_id):
    """If N replicas of winner-worker hit the same auction simultaneously,
    only one of them succeeds. (Rule 2: no two winners.)
    """
    key = f"auction:{auction_id}:closed"

    results = await asyncio.gather(
        *[redis_client.set(key, "1", nx=True, ex=60) for _ in range(20)]
    )
    wins = [r for r in results if r is True]
    losses = [r for r in results if not r]

    assert len(wins) == 1
    assert len(losses) == 19


async def test_permanent_marker_persists_after_ttl_overwrite(redis_client, auction_id):
    """After the worker writes winner_id to DB, it overwrites the closed key
    without TTL — late bids must still be rejected indefinitely.
    """
    key = f"auction:{auction_id}:closed"

    # initial claim with TTL
    await redis_client.set(key, "1", nx=True, ex=60)
    # finalize: drop the TTL
    await redis_client.set(key, "1")

    ttl = await redis_client.ttl(key)
    # -1 = no TTL set (permanent)
    assert ttl == -1
    assert await redis_client.get(key) == b"1"
