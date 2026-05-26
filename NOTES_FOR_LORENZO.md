# Notes for Lorenzo — WebSocket client contract

Hi Lorenzo. The WS protocol I implemented matches
`references/protocol.md` exactly **with the small clarifications below**.
None of these are breaking divergences from the reference, but they're
things you'll hit when writing the client.

## 1. Numbers come over the wire as strings, not JSON numbers

Pydantic serializes `Decimal` to a JSON string for safety (no float
precision loss). Concretely:

```json
// AuctionState
{ "type": "auction_state", "current_bid": "120.00", ... }

// BidAccepted
{ "type": "bid_accepted", "amount": "150.00", ... }
```

So in JS:

```js
const current = parseFloat(msg.current_bid);
const amount  = parseFloat(msg.amount);
```

When you send `place_bid`, either format is accepted (Pydantic coerces):

```json
{ "type": "place_bid", "amount": 150.00 }
{ "type": "place_bid", "amount": "150.00" }
```

I'd recommend sending as a **string** to avoid float weirdness on amounts
like `0.10` or `99.99`.

## 2. Timestamps are ISO-8601 UTC with `Z`

```json
{ "ends_at": "2026-06-19T20:00:00Z", "at": "2026-06-18T14:32:01Z" }
```

`new Date(msg.ends_at)` works in every browser.

## 3. Nullable fields

These can legally be `null`:

- `AuctionState.leader_user_id` — null when no bids placed yet.
- `AuctionClosed.winner_id` — null when auction ended with zero bids.
- `AuctionClosed.winning_amount` — null when `winner_id` is null.

So the UI needs an "auction ended with no winner" state.

## 4. `bid_rejected` is sent only to the bidder

Other clients in the room do **not** see rejections — only the bidder
who attempted them. The four reasons are:

| reason             | when                                          |
|--------------------|-----------------------------------------------|
| `too_low`          | amount ≤ current highest                      |
| `auction_closed`   | past `end_time` or already declared           |
| `self_bid`         | the bidder is the auction's owner             |
| `not_authenticated`| (reserved; today the socket is closed 4401)   |

`not_authenticated` is in the protocol enum but in the current
implementation auth failures **close the socket with code 4401** instead
of sending a rejection. Treat both as "auth problem" in your error UI.

## 5. `auction_closed` is broadcast

Unlike `bid_rejected`, this is fanned out to everyone connected to the
room — driven by the standalone winner-worker, not by anyone's bid.
There's no client message that triggers it.

## 6. Close codes you'll see

| code | meaning                                  | UX suggestion                |
|------|------------------------------------------|------------------------------|
| 1000 | normal close                             | nothing                      |
| 4401 | bad/missing JWT                          | redirect to login            |
| 4403 | forbidden (reserved; unused today)       | toast                        |
| 4404 | auction id doesn't exist                 | "auction not found" page     |
| 4408 | server closed because you went idle 60s  | offer reconnect button       |

The 60-second idle timeout is **server-driven**. If you want to keep the
connection open while the user just watches, send a `{"type":"ping"}`
every ~30s — server replies with `{"type":"pong"}`.

## 7. Token in the query string

```
ws://host:8000/ws/auctions/42?token=<jwt-from-/auth/login>
```

URL-encode the token if your transport touches it. Browsers' `WebSocket`
constructor does not encode for you.

## 8. Order of messages on connect

1. (browser) `new WebSocket(url)`
2. (server) sends **exactly one** `auction_state` frame, then enters the
   normal loop.

So your client can assume the first frame is always `auction_state` and
key off `type` from then on.

— Arthur
