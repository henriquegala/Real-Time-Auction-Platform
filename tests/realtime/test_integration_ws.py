"""End-to-end integration test against a running stack.

Skipped by default. To run:

  1. docker compose up -d  (need redis, db, backend, winner-worker)
  2. seed an auction via Henrique's API (or pre-insert)
  3. export AUCTION_WS_HOST=localhost:8000
     export AUCTION_TEST_TOKENS=<jwt1>,<jwt2>,<jwt3>,...
     export AUCTION_TEST_ID=<auction_id>
  4. pytest tests/realtime/test_integration_ws.py -v

Or just run the load-bidders script directly:

  python scripts/load_bidders.py --auction-id 1 --bidders 20 --duration 10 \\
      --host localhost:8000 --tokens <comma-separated-jwts>

Expected outcome (rules 1, 2 under contention):
  * exactly one bidder ends with the highest accepted amount
  * no two `bid_accepted` messages share the same amount
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from collections import Counter

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _config():
    host = os.environ.get("AUCTION_WS_HOST")
    tokens = os.environ.get("AUCTION_TEST_TOKENS")
    auction_id = os.environ.get("AUCTION_TEST_ID")
    if not (host and tokens and auction_id):
        pytest.skip(
            "integration test needs AUCTION_WS_HOST, AUCTION_TEST_TOKENS, AUCTION_TEST_ID"
        )
    return host, tokens.split(","), int(auction_id)


async def test_concurrent_bidders_have_at_most_one_winner_per_amount():
    websockets = pytest.importorskip("websockets")

    host, tokens, auction_id = _config()
    duration = float(os.environ.get("AUCTION_TEST_DURATION", "5"))
    n_bidders = min(len(tokens), int(os.environ.get("AUCTION_TEST_BIDDERS", "10")))

    accepted: list[tuple[float, int]] = []
    rejected: Counter[str] = Counter()

    async def bidder(idx: int, token: str):
        url = f"ws://{host}/ws/auctions/{auction_id}?token={token}"
        try:
            async with websockets.connect(url) as ws:
                state = json.loads(await ws.recv())
                current = float(state.get("current_bid", 0))

                async def reader():
                    while True:
                        msg = json.loads(await ws.recv())
                        if msg["type"] == "bid_accepted":
                            accepted.append((float(msg["amount"]), int(msg["bidder_id"])))
                        elif msg["type"] == "bid_rejected":
                            rejected[msg["reason"]] += 1

                reader_task = asyncio.create_task(reader())
                end = time.monotonic() + duration
                while time.monotonic() < end:
                    await asyncio.sleep(0.05 + 0.1 * (idx % 3))
                    current += 1 + (idx % 5)
                    await ws.send(json.dumps({"type": "place_bid", "amount": round(current, 2)}))
                reader_task.cancel()
        except Exception as e:
            pytest.fail(f"bidder {idx} crashed: {e}")

    await asyncio.gather(*[bidder(i, tokens[i % len(tokens)]) for i in range(n_bidders)])

    assert accepted, f"no bids accepted; rejected={dict(rejected)}"
    amounts = [a for a, _ in accepted]
    dup = [a for a, c in Counter(amounts).items() if c > 1]
    assert not dup, f"duplicate accepted amounts (atomicity bug): {dup}"
