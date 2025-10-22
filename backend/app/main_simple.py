from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from typing import List, Optional
from pydantic import BaseModel
import logging
from .services.currency_service import currency_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Pydantic models
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

    class Config:
        json_encoders = {
            float: lambda v: round(v, 8) if v is not None else None
        }

class PriceAlert(BaseModel):
    id: int
    symbol: str
    threshold_price: float
    alert_type: str
    message: Optional[str] = None
    is_active: bool = True
    created_at: str

class PriceAlertCreate(BaseModel):
    symbol: str
    threshold_price: float
    alert_type: str
    message: Optional[str] = None

class PriceAlertUpdate(BaseModel):
    threshold_price: Optional[float] = None
    alert_type: Optional[str] = None
    message: Optional[str] = None
    is_active: Optional[bool] = None

class TrackedSymbol(BaseModel):
    symbol: str
    name: str
    active: bool = True
    last_updated: str

# In-memory storage for demo
portfolio_items = [
    {
        "id": 1,
        "symbol": "BTC",
        "amount": 0.5,
        "price_buy": 30000,
        "purchase_date": "2024-01-15",
        "base_currency": "USD",
        "purchase_price_eur": 28000,
        "purchase_price_czk": 700000,
        "source": "Binance",
        "commission": 15.0,
        "total_investment_text": "$15,015",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T10:00:00Z",
        "current_price": 45000,
        "current_value": 22500,
        "pnl": 7500,
        "pnl_percent": 50.0
    },
    {
        "id": 2,
        "symbol": "ETH",
        "amount": 2.0,
        "price_buy": 2000,
        "purchase_date": "2024-02-20",
        "base_currency": "USD",
        "purchase_price_eur": 1850,
        "purchase_price_czk": 46000,
        "source": "Coinbase",
        "commission": 20.0,
        "total_investment_text": "$4,020",
        "created_at": "2024-02-20T14:30:00Z",
        "updated_at": "2024-02-20T14:30:00Z",
        "current_price": 2500,
        "current_value": 5000,
        "pnl": 1000,
        "pnl_percent": 25.0
    },
    {
        "id": 3,
        "symbol": "ADA",
        "amount": 1000,
        "price_buy": 0.5,
        "purchase_date": "2024-03-10",
        "base_currency": "USD",
        "purchase_price_eur": 0.46,
        "purchase_price_czk": 11.5,
        "source": "Kraken",
        "commission": 5.0,
        "total_investment_text": "$505",
        "created_at": "2024-03-10T09:15:00Z",
        "updated_at": "2024-03-10T09:15:00Z",
        "current_price": 0.6,
        "current_value": 600,
        "pnl": 100,
        "pnl_percent": 20.0
    }
]

alerts = [
    {
        "id": 1,
        "symbol": "BTC",
        "threshold_price": 50000,
        "alert_type": "above",
        "message": "BTC price above $50,000",
        "is_active": True,
        "created_at": "2024-01-15T10:00:00Z"
    },
    {
        "id": 2,
        "symbol": "ETH",
        "threshold_price": 2000,
        "alert_type": "below",
        "message": "ETH price below $2,000",
        "is_active": True,
        "created_at": "2024-02-20T14:30:00Z"
    }
]

tracked_symbols = [
    {
        "symbol": "BTC",
        "name": "Bitcoin",
        "active": True,
        "last_updated": "2024-10-22T18:20:00Z"
    },
    {
        "symbol": "ETH",
        "name": "Ethereum",
        "active": True,
        "last_updated": "2024-10-22T18:20:00Z"
    },
    {
        "symbol": "ADA",
        "name": "Cardano",
        "active": True,
        "last_updated": "2024-10-22T18:20:00Z"
    }
]

next_id = 4

def convert_portfolio_item(item: dict, target_currency: str) -> dict:
    """Convert a portfolio item to target currency"""
    if item["base_currency"] == target_currency:
        return item
    
    # Convert all price values
    converted_item = item.copy()
    converted_item["base_currency"] = target_currency
    
    # Convert buy price
    converted_item["price_buy"] = currency_service.convert_amount(
        item["price_buy"], item["base_currency"], target_currency
    )
    
    # Convert current price
    if item.get("current_price"):
        converted_item["current_price"] = currency_service.convert_amount(
            item["current_price"], item["base_currency"], target_currency
        )
    
    # Convert current value
    if item.get("current_value"):
        converted_item["current_value"] = currency_service.convert_amount(
            item["current_value"], item["base_currency"], target_currency
        )
    
    # Convert P&L
    if item.get("pnl"):
        converted_item["pnl"] = currency_service.convert_amount(
            item["pnl"], item["base_currency"], target_currency
        )
    
    # Convert commission
    if item.get("commission"):
        converted_item["commission"] = currency_service.convert_amount(
            item["commission"], item["base_currency"], target_currency
        )
    
    return converted_item


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting Crypto AI Agent API v2.0 (Simple Mode)")
    logger.info("✅ Running without external databases for demo")
    logger.info("💱 Initializing currency exchange rates...")
    await currency_service.get_exchange_rates()
    logger.info("✅ Currency service initialized")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Crypto AI Agent API v2.0")


app = FastAPI(
    title="Crypto AI Agent API",
    description="High-performance crypto portfolio management API (Demo Mode)",
    version="2.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "2.0.0", "mode": "demo"}

# Demo endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Crypto AI Agent API v2.0",
        "status": "running",
        "mode": "demo",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "portfolio": "/api/portfolio (coming soon)",
            "alerts": "/api/alerts (coming soon)"
        }
    }

# Portfolio CRUD endpoints
@app.get("/api/portfolio/", response_model=List[PortfolioItem])
async def get_portfolio(currency: str = "USD"):
    """Get all portfolio items converted to target currency"""
    converted_items = []
    for item in portfolio_items:
        converted_item = convert_portfolio_item(item, currency)
        converted_items.append(converted_item)
    return converted_items

@app.post("/api/portfolio/", response_model=PortfolioItem)
async def create_portfolio_item(item: PortfolioCreate):
    """Create a new portfolio item"""
    global next_id
    from datetime import datetime
    
    new_item = {
        "id": next_id,
        "symbol": item.symbol,
        "amount": item.amount,
        "price_buy": item.price_buy,
        "purchase_date": item.purchase_date,
        "base_currency": item.base_currency,
        "purchase_price_eur": None,
        "purchase_price_czk": None,
        "source": item.source,
        "commission": item.commission,
        "total_investment_text": item.total_investment_text,
        "created_at": datetime.now().isoformat() + "Z",
        "updated_at": datetime.now().isoformat() + "Z",
        "current_price": round(item.price_buy, 8),  # Demo: set current price same as buy price
        "current_value": round(item.amount * item.price_buy, 8),
        "pnl": 0.0,
        "pnl_percent": 0.0
    }
    
    portfolio_items.append(new_item)
    next_id += 1
    return new_item

@app.put("/api/portfolio/{item_id}", response_model=PortfolioItem)
async def update_portfolio_item(item_id: int, item: PortfolioUpdate):
    """Update a portfolio item"""
    from datetime import datetime
    
    for i, existing_item in enumerate(portfolio_items):
        if existing_item["id"] == item_id:
            # Update only provided fields
            update_data = item.dict(exclude_unset=True)
            for key, value in update_data.items():
                existing_item[key] = value
            
            existing_item["updated_at"] = datetime.now().isoformat() + "Z"
            
            # Recalculate values with 8 decimal precision
            existing_item["current_value"] = round(existing_item["amount"] * existing_item["current_price"], 8)
            total_investment = round(existing_item["amount"] * existing_item["price_buy"] + existing_item["commission"], 8)
            existing_item["pnl"] = round(existing_item["current_value"] - total_investment, 8)
            existing_item["pnl_percent"] = round((existing_item["pnl"] / total_investment) * 100, 8) if total_investment > 0 else 0
            
            return existing_item
    
    raise HTTPException(status_code=404, detail="Portfolio item not found")

@app.delete("/api/portfolio/{item_id}")
async def delete_portfolio_item(item_id: int):
    """Delete a portfolio item"""
    global portfolio_items
    original_length = len(portfolio_items)
    portfolio_items = [item for item in portfolio_items if item["id"] != item_id]
    
    if len(portfolio_items) == original_length:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    
    return {"message": "Portfolio item deleted successfully"}

@app.get("/api/portfolio/summary")
async def get_portfolio_summary(currency: str = "USD"):
    """Get portfolio summary converted to target currency"""
    # Convert all items to target currency first
    converted_items = []
    for item in portfolio_items:
        converted_item = convert_portfolio_item(item, currency)
        converted_items.append(converted_item)
    
    total_value = sum(item["current_value"] for item in converted_items)
    total_pnl = sum(item["pnl"] for item in converted_items)
    total_pnl_percent = (total_pnl / (total_value - total_pnl)) * 100 if total_value > total_pnl else 0
    
    return {
        "total_value": round(total_value, 8),
        "total_pnl": round(total_pnl, 8),
        "total_pnl_percent": round(total_pnl_percent, 8),
        "item_count": len(converted_items),
        "currency": currency
    }

# Alerts CRUD endpoints
@app.get("/api/alerts/", response_model=List[PriceAlert])
async def get_alerts(active_only: bool = True):
    """Get all alerts"""
    if active_only:
        return [alert for alert in alerts if alert["is_active"]]
    return alerts

@app.post("/api/alerts/", response_model=PriceAlert)
async def create_alert(alert: PriceAlertCreate):
    """Create a new alert"""
    global next_id
    from datetime import datetime
    
    new_alert = {
        "id": next_id,
        "symbol": alert.symbol,
        "threshold_price": alert.threshold_price,
        "alert_type": alert.alert_type,
        "message": alert.message,
        "is_active": True,
        "created_at": datetime.now().isoformat() + "Z"
    }
    
    alerts.append(new_alert)
    next_id += 1
    return new_alert

@app.put("/api/alerts/{alert_id}", response_model=PriceAlert)
async def update_alert(alert_id: int, alert: PriceAlertUpdate):
    """Update an alert"""
    from datetime import datetime
    
    for i, existing_alert in enumerate(alerts):
        if existing_alert["id"] == alert_id:
            update_data = alert.dict(exclude_unset=True)
            for key, value in update_data.items():
                existing_alert[key] = value
            return existing_alert
    
    raise HTTPException(status_code=404, detail="Alert not found")

@app.delete("/api/alerts/{alert_id}")
async def delete_alert(alert_id: int):
    """Delete an alert"""
    global alerts
    original_length = len(alerts)
    alerts = [alert for alert in alerts if alert["id"] != alert_id]
    
    if len(alerts) == original_length:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return {"message": "Alert deleted successfully"}

# Symbols endpoints
@app.get("/api/symbols/tracked", response_model=List[TrackedSymbol])
async def get_tracked_symbols(active_only: bool = True):
    """Get tracked symbols"""
    if active_only:
        return [symbol for symbol in tracked_symbols if symbol["active"]]
    return tracked_symbols

@app.post("/api/currency/refresh")
async def refresh_exchange_rates():
    """Refresh exchange rates from external API"""
    try:
        await currency_service.refresh_rates()
        return {
            "message": "Exchange rates refreshed successfully",
            "rates_count": len(currency_service.rates),
            "last_updated": currency_service.last_updated
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh exchange rates: {str(e)}")

@app.get("/api/currency/rates")
async def get_exchange_rates():
    """Get current exchange rates"""
    return {
        "base_currency": currency_service.base_currency,
        "rates": currency_service.rates,
        "last_updated": currency_service.last_updated
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main_simple:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
