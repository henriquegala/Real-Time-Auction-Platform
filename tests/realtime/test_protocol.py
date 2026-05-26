"""Schema tests — guards the WS contract that lives in references/protocol.md.

If a test in this file fails the frontend client will break. Update
NOTES_FOR_LORENZO.md before changing any assertion here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.realtime.protocol import (
    AuctionClosed,
    AuctionState,
    BidAccepted,
    BidRejected,
    ClientMessageAdapter,
    CloseCode,
    PlaceBid,
    Ping,
    Pong,
)


def test_place_bid_parses_from_client():
    msg = ClientMessageAdapter.validate_python({"type": "place_bid", "amount": "150.00"})
    assert isinstance(msg, PlaceBid)
    assert msg.amount == Decimal("150.00")


def test_ping_parses_from_client():
    msg = ClientMessageAdapter.validate_python({"type": "ping"})
    assert isinstance(msg, Ping)


def test_unknown_client_type_rejected():
    with pytest.raises(Exception):
        ClientMessageAdapter.validate_python({"type": "drop_table", "amount": "1"})


def test_place_bid_requires_positive_amount():
    with pytest.raises(Exception):
        ClientMessageAdapter.validate_python({"type": "place_bid", "amount": "0"})
    with pytest.raises(Exception):
        ClientMessageAdapter.validate_python({"type": "place_bid", "amount": "-5"})


def test_server_messages_serialize_to_protocol_shape():
    state = AuctionState(
        auction_id=42,
        item="Vintage Watch",
        current_bid=Decimal("120.00"),
        leader_user_id=7,
        ends_at=datetime(2026, 6, 19, 20, 0, 0, tzinfo=timezone.utc),
        owner_id=3,
    ).model_dump(mode="json")
    assert state["type"] == "auction_state"
    assert state["auction_id"] == 42
    assert state["item"] == "Vintage Watch"
    assert state["leader_user_id"] == 7
    assert state["owner_id"] == 3

    accepted = BidAccepted(
        auction_id=42,
        amount=Decimal("150.00"),
        bidder_id=11,
        bidder_name="arthur",
        at=datetime(2026, 6, 18, 14, 32, 1, tzinfo=timezone.utc),
    ).model_dump(mode="json")
    assert accepted["type"] == "bid_accepted"
    assert accepted["bidder_name"] == "arthur"

    closed = AuctionClosed(
        auction_id=42, winner_id=11, winning_amount=Decimal("150.00")
    ).model_dump(mode="json")
    assert closed["type"] == "auction_closed"
    assert closed["winner_id"] == 11

    assert Pong().model_dump()["type"] == "pong"


def test_bid_rejected_reasons_match_protocol():
    for reason in ("too_low", "auction_closed", "self_bid", "not_authenticated"):
        assert BidRejected(reason=reason).model_dump()["reason"] == reason

    with pytest.raises(Exception):
        BidRejected(reason="not_a_real_reason")  # type: ignore[arg-type]


def test_close_codes_match_protocol():
    assert CloseCode.NORMAL == 1000
    assert CloseCode.AUTH_FAILED == 4401
    assert CloseCode.FORBIDDEN == 4403
    assert CloseCode.NOT_FOUND == 4404
    assert CloseCode.IDLE_TIMEOUT == 4408
