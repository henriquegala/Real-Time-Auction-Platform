"""FastAPI app entrypoint.

NOTE FOR HENRIQUE: this file is a placeholder. Replace / extend with your
auth + auctions routers and lifespan. The realtime module needs the
include_router line below to remain, plus the lifespan additions documented
in app/realtime/README (Phase 2): app.state.redis, app.state.ws_manager,
app.state.jwt_secret, and the pubsub background task.
"""
from fastapi import FastAPI

from app.realtime.routes import router as realtime_router

app = FastAPI(title="Real-time Auction Platform")
app.include_router(realtime_router)
