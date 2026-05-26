"""
load_bidders.py — concurrency smoke test for the auction realtime layer.

Spawns N WebSocket clients on the same auction and has them race bids.
Expected outcome: exactly one final winner; no two bid_accepted messages
share the same amount.

Requires: pip install websockets

Usage:
  python load_bidders.py --auction-id 1 --bidders 20 --duration 10 \\
      --host localhost:8000 --token <jwt>

For a real test you need real JWTs for distinct users. The simplest path:
log in once per user via Henrique's /auth/login and pass a comma-separated
list via --tokens.
"""
import argparse
import asyncio
import json
import random
import time
from collections import Counter

import websockets


async def bidder(name: str, url: str, duration: float, accepted: list, rejected: Counter):
    end = time.monotonic() + duration
    try:
        async with websockets.connect(url) as ws:
            # initial state
            state = json.loads(await ws.recv())
            current = float(state.get("current_bid", 0))

            async def reader():
                while True:
                    msg = json.loads(await ws.recv())
                    if msg["type"] == "bid_accepted":
                        accepted.append((msg["amount"], msg["bidder_id"], name))
                    elif msg["type"] == "bid_rejected":
                        rejected[msg["reason"]] += 1

            reader_task = asyncio.create_task(reader())

            while time.monotonic() < end:
                await asyncio.sleep(random.uniform(0.05, 0.3))
                current += random.uniform(1, 5)
                await ws.send(json.dumps({"type": "place_bid", "amount": round(current, 2)}))

            reader_task.cancel()
    except Exception as e:
        print(f"[{name}] error: {e}")


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--auction-id", type=int, required=True)
    p.add_argument("--bidders", type=int, default=10)
    p.add_argument("--duration", type=float, default=10)
    p.add_argument("--host", default="localhost:8000")
    p.add_argument("--tokens", help="Comma-separated JWTs, one per bidder. "
                                    "If fewer than --bidders, tokens are cycled.")
    p.add_argument("--token", help="Single JWT used by all bidders (only valid if "
                                   "your backend doesn't enforce one socket per user).")
    args = p.parse_args()

    if args.tokens:
        tokens = args.tokens.split(",")
    elif args.token:
        tokens = [args.token]
    else:
        raise SystemExit("Provide --token or --tokens")

    accepted: list = []
    rejected: Counter = Counter()

    tasks = []
    for i in range(args.bidders):
        tok = tokens[i % len(tokens)]
        url = f"ws://{args.host}/ws/auctions/{args.auction_id}?token={tok}"
        tasks.append(bidder(f"b{i}", url, args.duration, accepted, rejected))

    await asyncio.gather(*tasks)

    print("\n=== RESULTS ===")
    print(f"accepted: {len(accepted)}")
    print(f"rejected: {dict(rejected)}")

    if accepted:
        accepted.sort(key=lambda x: x[0])
        amounts = [a for a, _, _ in accepted]
        winner = accepted[-1]
        print(f"highest accepted: {winner[0]} by bidder_id={winner[1]} ({winner[2]})")

        dup_amounts = [a for a, c in Counter(amounts).items() if c > 1]
        if dup_amounts:
            print(f"⚠️  duplicate accepted amounts: {dup_amounts}")
            print("    this is a CONCURRENCY BUG — atomic check failed")
        else:
            print("✅ no duplicate accepted amounts — atomicity holds")


if __name__ == "__main__":
    asyncio.run(main())
