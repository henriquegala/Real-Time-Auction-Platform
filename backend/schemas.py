from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")

class UserRegister(UserBase):
    password: str = Field(..., min_length=6, max_length=100)

class UserLogin(UserBase):
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class AuctionCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    starting_price: float = Field(..., gt=0.0)
    end_time: datetime

    @field_validator('end_time')
    @classmethod
    def validate_end_time(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        
        if v <= datetime.now(timezone.utc):
            raise ValueError("O tempo de encerramento do leilão tem de ser no futuro.")
        return v

class AuctionResponse(BaseModel):
    id: int
    creator_id: int
    title: str
    description: Optional[str]
    starting_price: float
    end_time: datetime
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class BidCreate(BaseModel):
    amount: float = Field(..., gt=0.0)

class BidResponse(BaseModel):
    id: int
    auction_id: int
    user_id: int
    amount: float
    created_at: datetime

    class Config:
        from_attributes = True
