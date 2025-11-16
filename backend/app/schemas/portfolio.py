from typing import Optional
from pydantic import BaseModel


class PortfolioItem(BaseModel):
    id: int
    symbol: str
    amount: float
    price_buy: float
    purchase_date: Optional[str] = None
    base_currency: str
    purchase_price_eur: Optional[float] = None
    purchase_price_czk: Optional[float] = None
    source: Optional[str] = None
    commission: float = 0.0
    total_investment_text: Optional[str] = None
    created_at: str
    updated_at: str
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    price_buy_usd: Optional[float] = None
    commission_usd: Optional[float] = None
    current_price_usd: Optional[float] = None
    current_value_usd: Optional[float] = None
    pnl_usd: Optional[float] = None
    pnl_percent_usd: Optional[float] = None
    exchange_rate_at_purchase: Optional[float] = None
    comments: Optional[str] = None

    class Config:
        json_encoders = {
            float: lambda v: round(v, 8) if v is not None else None
        }


class PortfolioCreate(BaseModel):
    symbol: str
    amount: float
    price_buy: float
    purchase_date: Optional[str] = None
    base_currency: str
    source: Optional[str] = None
    commission: float = 0.0
    total_investment_text: Optional[str] = None
    comments: Optional[str] = None

    class Config:
        json_encoders = {
            float: lambda v: round(v, 8) if v is not None else None
        }


class PortfolioUpdate(BaseModel):
    symbol: Optional[str] = None
    amount: Optional[float] = None
    price_buy: Optional[float] = None
    purchase_date: Optional[str] = None
    base_currency: Optional[str] = None
    source: Optional[str] = None
    commission: Optional[float] = None
    total_investment_text: Optional[str] = None
    comments: Optional[str] = None

    class Config:
        json_encoders = {
            float: lambda v: round(v, 8) if v is not None else None
        }
