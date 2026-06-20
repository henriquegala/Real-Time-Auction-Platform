import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from typing import List
from fastapi import FastAPI, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
import redis.asyncio as aioredis

import schemas
from database import get_db_cursor
from auth import hash_password, verify_password, create_access_token, decode_access_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Real-Time Auction Platform API",
    description="Backend API de suporte para leilões e gestão de concorrência.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

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

    await redis_client.set(f"auction:{new_auction[0]}:highest_bid", str(auction_data.starting_price))

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

    cached_highest = await redis_client.get(f"auction:{auction_id}:highest_bid")
    price = float(cached_highest) if cached_highest else float(db_auction[4])

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

@app.post("/api/auctions/{auction_id}/bids", response_model=schemas.BidResponse)
async def place_bid(
    auction_id: int,
    bid_data: schemas.BidCreate,
    current_user: schemas.UserResponse = Depends(get_current_user)
):
    """
    Submete uma nova licitação concorrente.
    Garante atomicidade e prevenção de "double winners" através de Optimistic Locking no Redis.
    """
    with get_db_cursor() as cursor:
        cursor.execute("SELECT creator_id, end_time, is_active, starting_price FROM auctions WHERE id = %s;", (auction_id,))
        auction = cursor.fetchone()
        
    if not auction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leilão não encontrado.")
        
    creator_id, end_time, is_active, starting_price = auction
    
    if current_user.id == creator_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não pode licitar no seu próprio leilão.")

    if not is_active or datetime.now(timezone.utc) >= end_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este leilão já se encontra encerrado.")

    redis_key = f"auction:{auction_id}:highest_bid"
    
    async with redis_client.pipeline() as pipe:
        try:
            await pipe.watch(redis_key)
            
            current_highest = await pipe.get(redis_key)
            current_limit = float(current_highest) if current_highest else float(starting_price)
            
            if bid_data.amount <= current_limit:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"A sua licitação deve ser superior a {current_limit}."
                )
                
            pipe.multi()
            pipe.set(redis_key, str(bid_data.amount))
            await pipe.execute()
            
        except aioredis.WatchError:
            logger.warning(f" Race Condition detetada no Leilão ID {auction_id}. Licitação de {bid_data.amount} rejeitada.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A sua licitação foi rejeitada porque outro utilizador efetuou uma oferta superior primeiro. Tente novamente."
            )

    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO bids (auction_id, bidder_id, amount)
            VALUES (%s, %s, %s)
            RETURNING id, auction_id, bidder_id, amount, created_at;
            """,
            (auction_id, current_user.id, bid_data.amount)
        )
        new_bid = cursor.fetchone()

    response_bid = schemas.BidResponse(
        id=new_bid[0],
        auction_id=new_bid[1],
        user_id=new_bid[2],
        amount=float(new_bid[3]),
        created_at=new_bid[4]
    )

    broadcast_message = {
        "event": "new_bid",
        "auction_id": auction_id,
        "amount": response_bid.amount,
        "username": current_user.username,
        "timestamp": response_bid.created_at.isoformat()
    }
    await redis_client.publish(f"auction:{auction_id}:events", json.dumps(broadcast_message))
    
    return response_bid

@app.websocket("/ws/auctions/{auction_id}")
async def websocket_auction_endpoint(websocket: WebSocket, auction_id: int):
    """
    WebSocket Canal Bidirecional em tempo real para atualizações de licitações.
    Lê do Redis Pub/Sub de forma assíncrona e envia para todos os visualizadores [13, 14].
    """
    await websocket.accept()
    
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"auction:{auction_id}:events")
    
    logger.info(f"Cliente WebSocket ligado ao Leilão ID {auction_id}.")
    
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                await websocket.send_text(message["data"])
            
            await asyncio.sleep(0.01)
            
    except WebSocketDisconnect:
        logger.info(f"Cliente WebSocket desconectou-se do Leilão ID {auction_id}.")
    except Exception as e:
        logger.error(f"Erro no canal WebSocket do Leilão ID {auction_id}: {e}")
    finally:
        await pubsub.unsubscribe(f"auction:{auction_id}:events")
        await pubsub.close()
        try:
            await websocket.close()
        except Exception:
            pass
