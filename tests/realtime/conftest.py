"""Shared fixtures for realtime tests.

Two redis fixtures are exposed:
  - `redis_client`  — fakeredis (default; runs anywhere, no daemon needed)
  - `real_redis`    — talks to REDIS_URL env var; skipped if unreachable

Both load `app/realtime/lua/bid.lua` and expose the cached sha as `bid_sha`.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
import pytest_asyncio

LUA_PATH = Path(__file__).resolve().parents[2] / "app" / "realtime" / "lua" / "bid.lua"


@pytest.fixture(scope="session")
def lua_source() -> str:
    return LUA_PATH.read_text()


@pytest_asyncio.fixture
async def redis_client():
    """Fresh fakeredis instance per test. Supports EVALSHA + SCRIPT LOAD."""
    import fakeredis.aioredis

    client = fakeredis.aioredis.FakeRedis()
    try:
        yield client
    finally:
        await client.flushall()
        await client.aclose()


@pytest_asyncio.fixture
async def real_redis():
    """Real redis if REDIS_URL is reachable. Skips otherwise.

    Each test gets a unique key prefix to avoid cross-test interference.
    """
    from redis.asyncio import Redis

    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    client = Redis.from_url(url)
    try:
        await client.ping()
    except Exception:
        await client.aclose()
        pytest.skip(f"redis not reachable at {url}")
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def bid_sha(redis_client, lua_source) -> str:
    return await redis_client.script_load(lua_source)


@pytest.fixture
def auction_id() -> int:
    # Unique per test to prevent cross-test pollution if a redis is reused.
    return uuid.uuid4().int % 1_000_000_000
