from typing import Optional
from pydantic import BaseModel


class PriceAlert(BaseModel):
    id: int
    symbol: str
    threshold_price: float
    alert_type: str
    message: Optional[str] = None
    is_active: bool = True
    created_at: str
    threshold_price_usd: Optional[float] = None
    base_currency: Optional[str] = None
    exchange_rate_at_creation: Optional[float] = None


class PriceAlertCreate(BaseModel):
    symbol: str
    threshold_price: float
    alert_type: str
    message: Optional[str] = None
    base_currency: Optional[str] = None


class PriceAlertUpdate(BaseModel):
    symbol: Optional[str] = None
    threshold_price: Optional[float] = None
    alert_type: Optional[str] = None
    message: Optional[str] = None
    is_active: Optional[bool] = None
