# Real-Time Auction Platform 🔨

![Status](https://img.shields.io/badge/Status-Working%20MVP-brightgreen)
![Stack](https://img.shields.io/badge/Stack-FastAPI%20%7C%20Redis%20%7C%20PostgreSQL-blue)

Project developed for the **Laboratórios de Sistemas e Serviços (LSS)** course at
the University of Aveiro — *Project 02, Topic 5: Real-time Online Auction Platform*.

A concurrent, real-time auction system where multiple users bid in live auctions.
New bids are broadcast to every participant instantly over **WebSockets**, bid
concurrency is resolved atomically through **Redis**, and final results are
persisted in **PostgreSQL**.

---

## 👥 Team & Responsibilities

| Member | Area |
|--------|------|
| **Henrique Gala** | Backend REST API, Authentication & PostgreSQL (data layer) |
| **Arthur Spanó** | Concurrency, WebSockets, Redis Pub/Sub & winner declaration (real-time layer) |
| **Lorenzo Lima** | Frontend UI & DevOps integration (Docker / Nginx) |

---

## 🏗️ Architecture

```
                    ┌──────────────────────────────────────────┐
   Browser          │                Docker network            │
 ┌──────────┐  80   │  ┌────────────┐         ┌──────────────┐  │
 │ Frontend │◄─────►│  │   Nginx    │  /api   │   Backend    │  │
 │ (JS/HTML)│  WS   │  │ (frontend) │────────►│  FastAPI     │  │
 └──────────┘       │  │  reverse   │  /ws    │ REST + WS    │  │
                    │  │   proxy    │────────►│              │  │
                    │  └────────────┘         └──────┬───────┘  │
                    │                                 │ atomic   │
                    │                          ┌──────▼───────┐  │
                    │                          │    Redis     │  │
                    │   ┌───────────────┐      │ Pub/Sub +    │  │
                    │   │ winner-worker │◄────►│ Lua atomic   │  │
                    │   │ (closes ended │      │ bid script   │  │
                    │   │  auctions)    │      └──────┬───────┘  │
                    │   └───────┬───────┘             │          │
                    │           │   ┌─────────────────▼───────┐  │
                    │           └──►│      PostgreSQL          │  │
                    │               │ users / auctions / bids  │  │
                    │               └──────────────────────────┘  │
                    └──────────────────────────────────────────┘
```

The system is split into **five containers** orchestrated by Docker Compose:

| Service | Image / Build | Role | Exposed port |
|---------|---------------|------|--------------|
| `frontend` | `nginx:alpine` | Serves the static UI and reverse-proxies `/api` and `/ws` to the backend | **80** |
| `backend` | FastAPI (Python 3.11) | REST API (auth, auctions) **and** the WebSocket bid endpoint | internal only |
| `redis` | `redis:7-alpine` | Atomic bid arbitration (Lua) + Pub/Sub fan-out | 6379 |
| `db` | `postgres:16-alpine` | Source of truth: users, auctions, bids, winners | internal only |
| `winner-worker` | FastAPI image | Background worker that closes auctions at `end_time` and declares winners | internal only |

> The backend is intentionally **not** published to the host — all traffic enters
> through Nginx on port **80** (`http://localhost`). This keeps the API and database
> off the host network.

---

## ⚙️ How the real-time concurrency works

This is the core of the project (Topic 5: *WebSockets, Redis Pub/Sub, SQL, Atomic
Transactions*). Bids are **not** placed over REST — they travel over a single
authenticated WebSocket per auction.

1. **Connect** — the client opens `ws://host/ws/auctions/{id}?token=<jwt>`.
   The JWT (issued by `/api/auth/login`) is verified before the socket is accepted;
   a bad/missing token closes the connection with code `4401`.
2. **Initial state** — the server seeds Redis from the DB (idempotent *warm cache*)
   and sends exactly one `auction_state` frame.
3. **Place bid** — the client sends `{"type":"place_bid","amount":"150.00"}`.
   The server runs an **atomic Lua script** (`bid.lua`) inside Redis that, in a
   single uninterruptible step:
   - rejects the bid if the auction is closed or past `end_time`;
   - rejects it if `amount <= current_highest`;
   - otherwise sets the new highest bid + leader.

   Because the check-and-set is a single Lua call, **no two concurrent bids can
   both win** — there is no read-modify-write race.
4. **Persist then broadcast** — only after Redis accepts does the server `INSERT`
   the bid into PostgreSQL (Redis is cache + broker, the DB is the source of truth),
   then `PUBLISH` a `bid_accepted` event. A per-worker `pubsub_loop` fans the event
   out to every connected client in that auction's room.
5. **Winner declaration** — the standalone `winner-worker` polls for auctions past
   `end_time`, atomically claims each one with `SET ... NX EX` (so only one worker
   closes a given auction even with multiple replicas), writes `winner_id` /
   `closed_at` to the DB, and publishes a broadcast `auction_closed` event.

### The five invariants (all enforced, all tested)

1. A bid must strictly exceed the current highest. *(enforced in Lua)*
2. No two bids can both win. *(atomic Lua check-and-set)*
3. Auctions close exactly at `end_time`. *(Lua time check + winner-worker)*
4. Owners cannot bid on their own auctions. *(JWT `user_id` vs auction `creator_id`)*
5. Every accepted bid is persisted to SQL before it is broadcast.

---

## 📁 Project structure

```
.
├── compose.yml                 # 5-service orchestration
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                 # REST API (auth, auctions) + mounts the WS router
│   ├── auth.py                 # bcrypt + JWT (HS256)
│   ├── database.py             # sync psycopg2 connection pool (REST)
│   ├── schemas.py              # Pydantic request/response models
│   ├── db/init.sql             # schema (users, auctions, bids)
│   └── app/realtime/           # ◄── the real-time + concurrency layer
│       ├── routes.py           # WebSocket endpoint /ws/auctions/{id}
│       ├── bids.py             # bid handler: Lua → SQL persist → publish
│       ├── winner.py           # winner-worker (run as its own container)
│       ├── manager.py          # per-auction in-process room manager
│       ├── protocol.py         # Pydantic WS message schemas
│       ├── auth.py             # JWT verification for WS connections
│       ├── db.py               # async SQLAlchemy helpers
│       └── lua/bid.lua         # atomic check-and-set bid script
├── frontend/
│   ├── Dockerfile              # nginx
│   ├── nginx.conf              # serves UI, proxies /api and /ws
│   ├── index.html
│   └── app.js                  # SPA: auth, auction list, live bidding over WS
├── scripts/load_bidders.py     # concurrency smoke test (N racing bidders)
├── tests/realtime/             # pytest suite (Lua atomicity, protocol, locking)
├── NOTES_FOR_HENRIQUE.md       # historical handoff notes (DB / coupling)
└── NOTES_FOR_LORENZO.md        # historical handoff notes (WS client contract)
```

---

## 🚀 How to run

**Requirements:** Docker + Docker Compose.

```bash
# from the repository root
docker compose up --build
```

Wait for the health checks to go green, then open:

```
http://localhost
```

To stop and wipe all data (resets the database, re-runs init.sql on next start):

```bash
docker compose down -v
```

---

## 🕹️ How to use

1. **Register** an account (username + password, min. 6 chars), then **log in**.
2. From the dashboard, **create an auction** (title, description, starting price,
   end time) — or join an existing one.
3. Click **Participar** to enter an auction. The client opens a WebSocket and
   shows live state.
4. **Place bids** — each accepted bid updates the price for *all* viewers instantly.
   - Bidding below the current price → `bid_rejected: too_low`.
   - Bidding on your own auction → `bid_rejected: self_bid`.
5. When the timer expires, the `winner-worker` closes the auction and everyone
   connected receives an `auction_closed` event with the winner.

---

## 🔌 REST API (via Nginx, prefix `/api`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET  | `/api/health` | – | Liveness of DB + Redis |
| POST | `/api/auth/register` | – | Create account |
| POST | `/api/auth/login` | – | Returns a JWT (`access_token`) |
| GET  | `/api/auth/me` | Bearer | Current user |
| POST | `/api/auctions` | Bearer | Create an auction |
| GET  | `/api/auctions` | – | List active auctions |
| GET  | `/api/auctions/{id}` | – | Auction detail (live price from Redis) |
| WS   | `/ws/auctions/{id}?token=<jwt>` | JWT in query | **Live bidding channel** |

The full WebSocket message protocol (message shapes, reject reasons, close codes)
is documented in [`NOTES_FOR_LORENZO.md`](./NOTES_FOR_LORENZO.md).

---

## 🧪 Testing

**Unit / concurrency tests** (run against an in-process `fakeredis`, no daemon
needed). The Lua atomicity, the WS protocol schemas, and the winner-worker's
`SET NX` mutex are all covered:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # dev/test deps (pytest, fakeredis, …)
pytest -q                                 # → 20 passed, 1 skipped (integration)
```

**Load / concurrency smoke test** against a running stack (N WebSocket clients
racing bids on one auction; asserts no two accepted bids share an amount):

```bash
# log in a few users first to obtain JWTs, then:
python scripts/load_bidders.py --auction-id 1 --bidders 20 --duration 10 \
    --host localhost --tokens <jwt1>,<jwt2>,...
```

> Note: pass `--host localhost` (Nginx on port 80), since the backend is not
> published directly to the host.

---

## 🔧 Configuration (environment variables)

| Variable | Service(s) | Default | Purpose |
|----------|-----------|---------|---------|
| `DATABASE_URL` | backend, winner-worker | `postgresql://lss_user:…@db:5432/auction_db` | DB connection (auto-coerced to `asyncpg` for the async layer) |
| `REDIS_URL` | backend, winner-worker | `redis://redis:6379/0` | Redis connection |
| `JWT_SECRET_KEY` | backend | `lss_secure_shared_jwt_secret_2026` | HS256 signing/verification secret (must be shared across replicas) |
| `WINNER_POLL_INTERVAL` | winner-worker | `2` | Seconds between sweeps for ended auctions |
| `WINNER_LOCK_TTL` | winner-worker | `60` | TTL on the close lock (lets a crashed worker retry) |

---

## 🗄️ Database schema

```
users(id, username, password_hash, created_at)
auctions(id, creator_id→users, title, description, starting_price,
         end_time, is_active, created_at, winner_id→users, closed_at)
bids(id, auction_id→auctions, bidder_id→users, amount, created_at)
```

`winner_id` / `closed_at` are written by the `winner-worker` when an auction ends.

---

## ⚠️ Review notes & known limitations

This section is an honest account of the current state for the project report.

- **Single source of truth for bidding.** Earlier in development there were two
  parallel bid implementations (an inline REST path and the WebSocket layer).
  These have been **reconciled**: the WebSocket + Lua layer is now the only bid
  path, and the REST `place_bid` endpoint was removed to avoid divergent state.
- **Bid persistence is best-effort atomic across stores.** A bid is committed in
  Redis (Lua) *then* in PostgreSQL. If the SQL `INSERT` fails after Redis accepted,
  the two stores can briefly diverge for that auction. This is documented in
  `app/realtime/bids.py` and is acceptable for the project's scope; a production
  system would use an outbox/transactional pattern.
- **Authentication.** Passwords are hashed with bcrypt; JWTs are HS256 with a
  shared secret. The secret and DB credentials are committed defaults for ease of
  grading — they would be injected as secrets in a real deployment.
- **CORS** is open (`allow_origins=["*"]`, credentials disabled) because the SPA
  authenticates with a Bearer token, not cookies.
- **Scope.** Auctions are closed by a polling worker (default every 2s), so the
  effective close time is `end_time` + up to one poll interval.

---

## 📄 License

See [LICENSE](./LICENSE).
