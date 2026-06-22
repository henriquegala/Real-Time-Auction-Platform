import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import logging
import os
from typing import List
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import schemas
import auth as auth_module
from database import get_db_cursor
from auth import hash_password, verify_password, create_access_token, decode_access_token

# Real-time + concurrency layer (Arthur). The WebSocket endpoint, atomic Lua
# bid handler and winner declaration all live here and are the canonical bid
# path — there is intentionally no REST "place bid" endpoint.
from app.realtime.manager import ConnectionManager
from app.realtime.routes import router as realtime_router
from app.realtime.bids import load_bid_script, pubsub_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://lss_user:lss_secure_password@db:5432/auction_db"
)

# Single async Redis client, shared by the REST handlers and the realtime layer.
redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)


def _async_db_url(url: str) -> str:
    """Coerce a libpq/psycopg2 URL into the asyncpg form SQLAlchemy needs.

    The sync REST handlers use psycopg2 (`postgresql://`); the realtime layer
    needs an async engine (`postgresql+asyncpg://`). One env var drives both.
    """
    for prefix in ("postgresql+asyncpg://", ):
        if url.startswith(prefix):
            return url
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Wire the realtime layer onto app.state and run the Pub/Sub fan-out task."""
    engine = create_async_engine(_async_db_url(DATABASE_URL), pool_pre_ping=True)
    app.state.db_engine = engine
    app.state.db_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.redis = redis_client
    app.state.ws_manager = ConnectionManager()
    # Sign and verify with the exact same secret /api/auth/login uses.
    app.state.jwt_secret = auth_module.SECRET_KEY
    app.state.bid_script_sha = await load_bid_script(redis_client)

    pubsub_task = asyncio.create_task(pubsub_loop(app))
    try:
        yield
    finally:
        pubsub_task.cancel()
        try:
            await pubsub_task
        except (asyncio.CancelledError, Exception):
            pass
        await redis_client.aclose()
        await engine.dispose()


app = FastAPI(
    title="Real-Time Auction Platform API",
    description="Backend API de suporte para leilões e gestão de concorrência.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the WebSocket endpoint (/ws/auctions/{id}) from the realtime layer.
app.include_router(realtime_router)

@app.get("/api/health")
async def health_check():
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT 1;")
            db_status = "connected"
    except Exception:
        db_status = "disconnected"
        
    try:
        await redis_client.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"
        
    return {
        "status": "healthy",
        "database": db_status,
        "redis": redis_status
    }

@app.post("/api/auth/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: schemas.UserRegister):
    hashed_pwd = hash_password(user_data.password)
    
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id FROM users WHERE username = %s;", (user_data.username,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este nome de utilizador já se encontra registado."
            )
            
        cursor.execute(
            """
            INSERT INTO users (username, password_hash) 
            VALUES (%s, %s) 
            RETURNING id, username, created_at;
            """,
            (user_data.username, hashed_pwd)
        )
        new_user = cursor.fetchone()
        
    logger.info(f"Utilizador '{user_data.username}' registado com sucesso.")
    return schemas.UserResponse(
        id=new_user[0],
        username=new_user[1],
        created_at=new_user[2]
    )


@app.post("/api/auth/login", response_model=schemas.Token)
async def login_user(user_data: schemas.UserLogin):
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id, username, password_hash FROM users WHERE username = %s;", (user_data.username,))
        db_user = cursor.fetchone()
        
    if not db_user or not verify_password(user_data.password, db_user[2]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nome de utilizador ou palavra-passe incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(
        data={"sub": db_user[1], "user_id": db_user[0]},
        expires_delta=access_token_expires
    )
    
    return schemas.Token(access_token=access_token, token_type="bearer")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> schemas.UserResponse:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada. Efetue login novamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username: str = payload.get("sub")
    user_id: int = payload.get("user_id")
    
    if username is None or user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido. Assinatura corrompida.",
        )
        
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id, username, created_at FROM users WHERE id = %s;", (user_id,))
        db_user = cursor.fetchone()
        
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilizador não encontrado.",
        )
        
    return schemas.UserResponse(
        id=db_user[0],
        username=db_user[1],
        created_at=db_user[2]
    )


@app.get("/api/auth/me", response_model=schemas.UserResponse)
async def get_me(current_user: schemas.UserResponse = Depends(get_current_user)):
    return current_user

@app.post("/api/auctions", response_model=schemas.AuctionResponse, status_code=status.HTTP_201_CREATED)
async def create_auction(
    auction_data: schemas.AuctionCreate,
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO auctions (creator_id, title, description, starting_price, end_time)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, creator_id, title, description, starting_price, end_time, is_active, created_at;
            """,
            (
                current_user.id,
                auction_data.title,
                auction_data.description,
                auction_data.starting_price,
                auction_data.end_time
            )
        )
        new_auction = cursor.fetchone()

    # Redis state (current bid, leader, ends_at, closed) is seeded lazily by the
    # realtime layer's warm_cache() on the first WebSocket connection.
    logger.info(f"Leilão ID {new_auction[0]} criado pelo Utilizador ID {current_user.id}.")
    return schemas.AuctionResponse(
        id=new_auction[0],
        creator_id=new_auction[1],
        title=new_auction[2],
        description=new_auction[3],
        starting_price=float(new_auction[4]),
        end_time=new_auction[5],
        is_active=new_auction[6],
        created_at=new_auction[7]
    )


@app.get("/api/auctions", response_model=List[schemas.AuctionResponse])
async def list_active_auctions():
    now = datetime.now(timezone.utc)
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, creator_id, title, description, starting_price, end_time, is_active, created_at
            FROM auctions
            WHERE is_active = TRUE AND end_time > %s
            ORDER BY end_time ASC;
            """,
            (now,)
        )
        db_auctions = cursor.fetchall()

    return [
        schemas.AuctionResponse(
            id=row[0],
            creator_id=row[1],
            title=row[2],
            description=row[3],
            starting_price=float(row[4]),
            end_time=row[5],
            is_active=row[6],
            created_at=row[7]
        )
        for row in db_auctions
    ]


@app.get("/api/auctions/{auction_id}", response_model=schemas.AuctionResponse)
async def get_auction_details(auction_id: int):
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, creator_id, title, description, starting_price, end_time, is_active, created_at
            FROM auctions
            WHERE id = %s;
            """,
            (auction_id,)
        )
        db_auction = cursor.fetchone()

    if not db_auction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leilão não encontrado na base de dados."
        )

    cached_current = await redis_client.get(f"auction:{auction_id}:current")
    price = float(cached_current) if cached_current else float(db_auction[4])

    return schemas.AuctionResponse(
        id=db_auction[0],
        creator_id=db_auction[1],
        title=db_auction[2],
        description=db_auction[3],
        starting_price=price,
        end_time=db_auction[5],
        is_active=db_auction[6],
        created_at=db_auction[7]
    )

# Bids are NOT placed over REST. The live bid path is the WebSocket endpoint
# /ws/auctions/{id} (app.realtime.routes), which runs the atomic Lua script,
# persists to SQL and broadcasts via Redis Pub/Sub. See NOTES_FOR_LORENZO.md
# for the client message protocol.
