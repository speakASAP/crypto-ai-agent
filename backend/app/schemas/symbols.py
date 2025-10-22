from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TrackedSymbolBase(BaseModel):
    symbol: str = Field(..., max_length=10, description="Cryptocurrency symbol")
    is_active: bool = Field(True, description="Whether symbol is actively tracked")


class TrackedSymbolCreate(TrackedSymbolBase):
    pass


class TrackedSymbolUpdate(BaseModel):
    is_active: Optional[bool] = None


class TrackedSymbolResponse(TrackedSymbolBase):
    created_at: datetime
    
    class Config:
        from_attributes = True


class CryptoSymbolBase(BaseModel):
    symbol: str = Field(..., max_length=10, description="Cryptocurrency symbol")
    name: Optional[str] = Field(None, max_length=100, description="Full name")
    description: Optional[str] = Field(None, description="Description")
    is_tradable: bool = Field(True, description="Whether symbol is tradable")


class CryptoSymbolCreate(CryptoSymbolBase):
    pass


class CryptoSymbolUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    is_tradable: Optional[bool] = None


class CryptoSymbolResponse(CryptoSymbolBase):
    id: int
    last_updated: datetime
    
    class Config:
        from_attributes = True


class SymbolPrice(BaseModel):
    symbol: str
    price: float
    timestamp: datetime
