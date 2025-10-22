from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class PortfolioBase(BaseModel):
    symbol: str = Field(..., max_length=10, description="Cryptocurrency symbol")
    amount: Decimal = Field(..., gt=0, description="Amount of cryptocurrency")
    price_buy: Decimal = Field(..., gt=0, description="Purchase price")
    purchase_date: Optional[datetime] = Field(None, description="Purchase date")
    base_currency: str = Field(..., max_length=3, description="Base currency (USD, EUR, CZK)")
    source: Optional[str] = Field(None, max_length=50, description="Purchase source")
    commission: Decimal = Field(0, ge=0, description="Commission paid")


class PortfolioCreate(PortfolioBase):
    pass


class PortfolioUpdate(BaseModel):
    symbol: Optional[str] = Field(None, max_length=10)
    amount: Optional[Decimal] = Field(None, gt=0)
    price_buy: Optional[Decimal] = Field(None, gt=0)
    purchase_date: Optional[datetime] = None
    base_currency: Optional[str] = Field(None, max_length=3)
    source: Optional[str] = Field(None, max_length=50)
    commission: Optional[Decimal] = Field(None, ge=0)


class PortfolioResponse(PortfolioBase):
    id: int
    purchase_price_eur: Optional[Decimal] = None
    purchase_price_czk: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
    
    # Calculated fields
    current_price: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    pnl: Optional[Decimal] = None
    pnl_percent: Optional[Decimal] = None
    
    class Config:
        from_attributes = True


class PortfolioSummary(BaseModel):
    total_value: Decimal
    total_pnl: Decimal
    total_pnl_percent: Decimal
    currency: str
    item_count: int
