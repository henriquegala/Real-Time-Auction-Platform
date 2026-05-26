"""WebSocket message schemas.

Mirrors references/protocol.md. Any divergence here MUST be noted in
NOTES_FOR_LORENZO.md so the frontend client stays in sync.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter


# ---------------------------------------------------------------------------
# Client -> Server
# ---------------------------------------------------------------------------

class PlaceBid(BaseModel):
    type: Literal["place_bid"]
    amount: Decimal = Field(gt=0)


class Ping(BaseModel):
    type: Literal["ping"]


ClientMessage = Annotated[Union[PlaceBid, Ping], Field(discriminator="type")]
ClientMessageAdapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


# ---------------------------------------------------------------------------
# Server -> Client
# ---------------------------------------------------------------------------

class AuctionState(BaseModel):
    type: Literal["auction_state"] = "auction_state"
    auction_id: int
    item: str
    current_bid: Decimal
    leader_user_id: int | None
    ends_at: datetime
    owner_id: int


class BidAccepted(BaseModel):
    type: Literal["bid_accepted"] = "bid_accepted"
    auction_id: int
    amount: Decimal
    bidder_id: int
    bidder_name: str
    at: datetime


RejectReason = Literal[
    "too_low",
    "auction_closed",
    "self_bid",
    "not_authenticated",
]


class BidRejected(BaseModel):
    type: Literal["bid_rejected"] = "bid_rejected"
    reason: RejectReason


class AuctionClosed(BaseModel):
    type: Literal["auction_closed"] = "auction_closed"
    auction_id: int
    winner_id: int | None
    winning_amount: Decimal | None


class Pong(BaseModel):
    type: Literal["pong"] = "pong"


# ---------------------------------------------------------------------------
# Close codes
# ---------------------------------------------------------------------------

class CloseCode:
    NORMAL = 1000
    AUTH_FAILED = 4401
    FORBIDDEN = 4403
    NOT_FOUND = 4404
    IDLE_TIMEOUT = 4408
