"""Unit tests for the atomic bid Lua script.

These run against fakeredis by default (in-process, no daemon). The same
suite passes against a real redis by adding `pytestmark = pytest.mark.redis`
and pointing REDIS_URL at it. Lua semantics are identical.

The five hard rules of the project map onto specific tests below:
  rule 1 — bid must exceed current     -> test_rejects_equal / test_rejects_lower
  rule 2 — no two bids both win        -> test_concurrent_bids_serialize
  rule 3 — auctions close at end_time  -> test_rejects_after_end_time
                                          test_rejects_when_closed_flag_set
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.asyncio


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _keys(aid: int) -> list[str]:
    return [
        f"auction:{aid}:current",
        f"auction:{aid}:leader",
        f"auction:{aid}:ends_at",
        f"auction:{aid}:closed",
    ]


async def _seed(redis, aid: int, *, start: str = "100", ends_at: datetime | None = None) -> None:
    if ends_at is None:
        ends_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await redis.mset(
        {
            f"auction:{aid}:current": start,
            f"auction:{aid}:leader": "",
            f"auction:{aid}:ends_at": _iso(ends_at),
        }
    )


async def _eval(redis, sha: str, aid: int, amount: str, bidder: str, now: datetime | None = None):
    now_iso = _iso(now or datetime.now(timezone.utc))
    return await redis.evalsha(sha, len(_keys(aid)), *_keys(aid), amount, bidder, now_iso)


def _decode(result):
    return [
        x.decode() if isinstance(x, (bytes, bytearray)) else x for x in result
    ]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_accepts_first_bid_above_start(redis_client, bid_sha, auction_id):
    await _seed(redis_client, auction_id, start="100")

    result = _decode(await _eval(redis_client, bid_sha, auction_id, "150", "7"))

    assert result == ["ok", "150"]
    current = await redis_client.get(f"auction:{auction_id}:current")
    leader = await redis_client.get(f"auction:{auction_id}:leader")
    assert current == b"150"
    assert leader == b"7"


async def test_accepts_successive_increasing_bids(redis_client, bid_sha, auction_id):
    await _seed(redis_client, auction_id, start="100")

    assert _decode(await _eval(redis_client, bid_sha, auction_id, "110", "1"))[0] == "ok"
    assert _decode(await _eval(redis_client, bid_sha, auction_id, "120", "2"))[0] == "ok"
    assert _decode(await _eval(redis_client, bid_sha, auction_id, "130.50", "3"))[0] == "ok"

    assert await redis_client.get(f"auction:{auction_id}:current") == b"130.50"
    assert await redis_client.get(f"auction:{auction_id}:leader") == b"3"


# ---------------------------------------------------------------------------
# Rule 1 — must exceed current
# ---------------------------------------------------------------------------


async def test_rejects_equal_to_current(redis_client, bid_sha, auction_id):
    await _seed(redis_client, auction_id, start="100")
    result = _decode(await _eval(redis_client, bid_sha, auction_id, "100", "9"))
    assert result == ["err", "too_low"]


async def test_rejects_lower_than_current(redis_client, bid_sha, auction_id):
    await _seed(redis_client, auction_id, start="100")
    result = _decode(await _eval(redis_client, bid_sha, auction_id, "99.99", "9"))
    assert result == ["err", "too_low"]


async def test_rejected_bid_does_not_mutate_state(redis_client, bid_sha, auction_id):
    await _seed(redis_client, auction_id, start="100")
    await _eval(redis_client, bid_sha, auction_id, "50", "9")
    assert await redis_client.get(f"auction:{auction_id}:current") == b"100"
    assert await redis_client.get(f"auction:{auction_id}:leader") == b""


# ---------------------------------------------------------------------------
# Rule 3 — closed via end_time and via the closed flag
# ---------------------------------------------------------------------------


async def test_rejects_after_end_time(redis_client, bid_sha, auction_id):
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    await _seed(redis_client, auction_id, start="100", ends_at=past)
    result = _decode(await _eval(redis_client, bid_sha, auction_id, "200", "1"))
    assert result == ["err", "closed"]


async def test_rejects_when_closed_flag_set(redis_client, bid_sha, auction_id):
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    await _seed(redis_client, auction_id, start="100", ends_at=future)
    await redis_client.set(f"auction:{auction_id}:closed", "1")

    result = _decode(await _eval(redis_client, bid_sha, auction_id, "200", "1"))
    assert result == ["err", "closed"]


async def test_rejects_when_auction_missing(redis_client, bid_sha, auction_id):
    # never seeded
    result = _decode(await _eval(redis_client, bid_sha, auction_id, "200", "1"))
    assert result == ["err", "missing"]


# ---------------------------------------------------------------------------
# Rule 2 — atomicity under concurrency
# ---------------------------------------------------------------------------


async def test_concurrent_bids_serialize(redis_client, bid_sha, auction_id):
    """N bidders attempt the same amount concurrently — at most one wins it,
    and the leader equals exactly one of them. Multiple distinct higher
    amounts succeed sequentially without losing any.
    """
    await _seed(redis_client, auction_id, start="100")

    n = 30
    amount = "150"
    results = await asyncio.gather(
        *[_eval(redis_client, bid_sha, auction_id, amount, str(i)) for i in range(n)]
    )
    decoded = [_decode(r) for r in results]

    accepts = [r for r in decoded if r[0] == "ok"]
    rejects = [r for r in decoded if r[0] == "err"]

    # Exactly one bidder can win the SAME amount because the script does
    # `new_amt > current`. The first to land at 150 wins; everyone else
    # arriving at 150 sees current=150 and is rejected as too_low.
    assert len(accepts) == 1, f"expected 1 winner, got {len(accepts)}: {accepts}"
    assert all(r[1] == "too_low" for r in rejects)

    # The persisted leader must be a valid bidder id from the batch.
    leader = (await redis_client.get(f"auction:{auction_id}:leader")).decode()
    assert leader in {str(i) for i in range(n)}
    assert (await redis_client.get(f"auction:{auction_id}:current")) == b"150"


async def test_concurrent_distinct_amounts_no_loss(redis_client, bid_sha, auction_id):
    """When bidders submit distinct increasing amounts at the same time,
    the final state always reflects the highest one. No accepted bid is
    ever overwritten by a lower one (rule 1 under contention).
    """
    await _seed(redis_client, auction_id, start="100")

    amounts = list(range(101, 151))  # 50 distinct amounts
    results = await asyncio.gather(
        *[
            _eval(redis_client, bid_sha, auction_id, str(a), str(a))
            for a in amounts
        ]
    )
    decoded = [_decode(r) for r in results]
    accepted_amounts = sorted(int(r[1]) for r in decoded if r[0] == "ok")
    # Whatever order they landed in, the persisted current is the max accepted.
    final = int((await redis_client.get(f"auction:{auction_id}:current")).decode())
    assert final == max(accepted_amounts)
    # And the leader is that amount's bidder (they share an id in this test).
    leader = (await redis_client.get(f"auction:{auction_id}:leader")).decode()
    assert leader == str(final)
