from typing import Optional
from pydantic import BaseModel


class TrackedSymbol(BaseModel):
    symbol: str
    name: str | None = None
    is_active: bool = True
    created_at: str
    
    class Config:
        # Map backend 'active' field to frontend 'is_active'
        populate_by_name = True
    
    @classmethod
    def from_db_row(cls, row):
        """Convert database row to TrackedSymbol format expected by frontend"""
        return cls(
            symbol=row[0],
            name=row[1] if len(row) > 1 else row[0],
            is_active=bool(row[2]) if len(row) > 2 else True,
            created_at=row[3] if len(row) > 3 else row[1] if len(row) > 1 else ""
        )


class CryptoSymbol(BaseModel):
    symbol: str
    name: str
    market_cap_rank: Optional[int] = None
    last_updated: str


class CryptoSymbolSearch(BaseModel):
    query: str
    limit: int = 50
