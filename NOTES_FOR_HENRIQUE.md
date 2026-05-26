# Notes for Henrique — coupling points from the realtime layer

Hi Henrique. This file lists every assumption the realtime module
(`app/realtime/`) makes about your code. Nothing here is implemented by
me — please confirm or adjust and we sync up before the integration test.

## 1. Schema additions needed

The atomic bid handler reads/writes via raw SQL (`text()`) so I don't
hard-import your ORM classes. The realtime layer assumes the following
tables/columns exist. Two columns are **new** and must be added to your
`auctions` table:

### `auctions`
```sql
ALTER TABLE auctions ADD COLUMN winner_id INTEGER NULL REFERENCES users(id);
ALTER TABLE auctions ADD COLUMN closed_at TIMESTAMPTZ NULL;
```

Full set of columns the realtime layer reads from:

| column         | type           | used by                                |
|----------------|----------------|----------------------------------------|
| `id`           | INT PK         | everywhere                             |
| `item`         | TEXT           | `AuctionState` payload                 |
| `owner_id`     | INT (FK users) | self-bid rejection (rule 4)            |
| `start_price`  | NUMERIC        | warm-cache initial current bid         |
| `end_time`     | TIMESTAMPTZ    | winner job query, Lua close check      |
| `winner_id`    | INT NULL **(new)** | winner-worker UPDATE              |
| `closed_at`    | TIMESTAMPTZ NULL **(new)** | winner-worker UPDATE      |

### `bids`
```sql
-- I assume this table already exists in your design. Required columns:
-- id (PK), auction_id (FK), user_id (FK), amount (NUMERIC), created_at (TIMESTAMPTZ)
```

### `users`
Only `id` and `username` are read.

**I will not run migrations.** Once you've added `winner_id` / `closed_at`
to your Alembic revision (or schema script), the realtime layer picks
them up automatically — no further work from my side.

## 2. Session factory contract

`app/realtime/db.py` and `app/realtime/winner.py` use:

```python
async with session_factory() as session:
    await session.execute(text(...))
    await session.commit()
```

In the FastAPI app, I look it up as `app.state.db_session_factory` (set
in the lifespan). In `main.py` I provided a working default that creates
its own engine from `DATABASE_URL`. **When you wire in your routers, please
merge the lifespan instead of replacing it** — the `app.state.*` attrs
listed in the docstring at the top of `app/main.py` must all be set:

```
app.state.redis              # redis.asyncio.Redis
app.state.ws_manager         # ConnectionManager()
app.state.jwt_secret         # str
app.state.bid_script_sha     # str — return value of load_bid_script(redis)
app.state.db_session_factory # async_sessionmaker
```

If your engine setup looks different, all you need to do is point
`app.state.db_session_factory` at your existing `async_sessionmaker`. The
realtime layer never creates a second engine.

## 3. JWT shape

The WebSocket auth (`app/realtime/auth.py`) expects:

- HS256 signing
- secret from env var `JWT_SECRET` (same one your `/auth/login` signs with)
- `sub` claim contains the integer user id (cast via `int(payload["sub"])`)

If your token uses a different claim name or signs with RS256, ping me and
I'll adjust `authenticate_ws()` to match. **Right now the realtime module
will reject every connection if the claim layout differs.**

## 4. docker-compose

I appended two services in `docker-compose.yml` under a clearly-marked
section: `redis` and `winner-worker`. I did **not** touch (because they
don't exist yet) `db`, `backend`, `frontend`. When you add them:

- `backend` should `depends_on: redis: service_healthy` and set
  `REDIS_URL=redis://redis:6379/0` plus `JWT_SECRET=...` in its env.
- `winner-worker` already has a commented `db.condition: service_healthy`
  line — please uncomment it once your `db` service has a healthcheck.
- `winner-worker` uses `build: .` — it reuses the same Dockerfile as
  `backend`. If your Dockerfile lives elsewhere, adjust both lines.

## 5. Things I deliberately did NOT touch

- `/auth/login`, `/auth/register`, the User model — yours.
- Auction CRUD endpoints (`POST /auctions`, etc.) — yours.
- Migrations — yours.
- Dockerfile(s) for the backend image — yours.

## 6. How to verify the integration is wired up

```bash
docker compose up -d
# wait for healthchecks
python scripts/load_bidders.py --auction-id <id> --bidders 20 --duration 10 \
    --host localhost:8000 --tokens <jwt1>,<jwt2>,...
```

Expected output: `✅ no duplicate accepted amounts — atomicity holds`.

— Arthur
