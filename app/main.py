"""FastAPI app entrypoint.

NOTE FOR HENRIQUE
=================
This file is owned by you. The realtime module needs these four things to
exist on `app.state` by the time the WS endpoint is hit:

  app.state.redis              # redis.asyncio.Redis
  app.state.ws_manager         # ConnectionManager()
  app.state.jwt_secret         # str — same secret your /auth/login signs with
  app.state.bid_script_sha     # str — return value of load_bid_script(redis)
  app.state.db_session_factory # async_sessionmaker tied to your engine

Plus one background task: `pubsub_loop(app)`.

The lifespan below is a working default. When you wire in your routers and
your own engine, merge these lines into your lifespan instead of replacing it.
The only structural requirement from the realtime side is the single
`include_router(realtime_router)` call.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.realtime.bids import load_bid_script, pubsub_loop
from app.realtime.manager import ConnectionManager
from app.realtime.routes import router as realtime_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    database_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://auction:auction@db:5432/auction")
    jwt_secret = os.environ.get("JWT_SECRET", "dev-secret-change-me")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    app.state.db_engine = engine
    app.state.db_session_factory = async_sessionmaker(engine, expire_on_commit=False)

    app.state.redis = Redis.from_url(redis_url)
    app.state.ws_manager = ConnectionManager()
    app.state.jwt_secret = jwt_secret
    app.state.bid_script_sha = await load_bid_script(app.state.redis)

    pubsub_task = asyncio.create_task(pubsub_loop(app))
    try:
        yield
    finally:
        pubsub_task.cancel()
        try:
            await pubsub_task
        except (asyncio.CancelledError, Exception):
            pass
        await app.state.redis.aclose()
        await engine.dispose()


app = FastAPI(title="Real-time Auction Platform", lifespan=lifespan)
app.include_router(realtime_router)
