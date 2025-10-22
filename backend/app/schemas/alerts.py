from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal
from enum import Enum


class AlertType(str, Enum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"


class PriceAlertBase(BaseModel):
    symbol: str = Field(..., max_length=10, description="Cryptocurrency symbol")
    alert_type: AlertType = Field(..., description="Alert type (ABOVE or BELOW)")
    threshold_price: Decimal = Field(..., gt=0, description="Price threshold")
    message: Optional[str] = Field(None, description="Custom alert message")
    is_active: bool = Field(True, description="Whether alert is active")


class PriceAlertCreate(PriceAlertBase):
    pass


class PriceAlertUpdate(BaseModel):
    symbol: Optional[str] = Field(None, max_length=10)
    alert_type: Optional[AlertType] = None
    threshold_price: Optional[Decimal] = Field(None, gt=0)
    message: Optional[str] = None
    is_active: Optional[bool] = None


class PriceAlertResponse(PriceAlertBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AlertHistoryResponse(BaseModel):
    id: int
    alert_id: int
    symbol: str
    triggered_price: Decimal
    threshold_price: Decimal
    alert_type: AlertType
    message: Optional[str]
    triggered_at: datetime
    
    class Config:
        from_attributes = True


class AlertTrigger(BaseModel):
    symbol: str
    current_price: Decimal
    threshold_price: Decimal
    alert_type: AlertType
    message: Optional[str]
