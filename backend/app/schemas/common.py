from typing import Optional
from pydantic import BaseModel


class TrackedSymbol(BaseModel):
    symbol: str
    name: str
    active: bool = True
    last_updated: str


class CryptoSymbol(BaseModel):
    symbol: str
    name: str
    market_cap_rank: Optional[int] = None
    last_updated: str


class CryptoSymbolSearch(BaseModel):
    query: str
    limit: int = 50
