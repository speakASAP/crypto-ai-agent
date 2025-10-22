from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from typing import List, Optional

from app.core.database import get_db
from app.models.symbols import TrackedSymbol, CryptoSymbol
from app.schemas.symbols import (
    TrackedSymbolCreate, 
    TrackedSymbolUpdate, 
    TrackedSymbolResponse,
    CryptoSymbolCreate,
    CryptoSymbolUpdate,
    CryptoSymbolResponse,
    SymbolPrice
)
from app.services.cache_service import CacheService
from app.services.price_service import PriceService

router = APIRouter()


def get_cache_service() -> CacheService:
    """Dependency to get cache service"""
    return None


@router.get("/tracked", response_model=List[TrackedSymbolResponse])
async def get_tracked_symbols(
    active_only: bool = Query(True, description="Show only active symbols"),
    db: AsyncSession = Depends(get_db)
):
    """Get tracked cryptocurrency symbols"""
    try:
        query = select(TrackedSymbol)
        if active_only:
            query = query.where(TrackedSymbol.is_active == True)
        
        result = await db.execute(query)
        symbols = result.scalars().all()
        
        return [TrackedSymbolResponse(
            symbol=symbol.symbol,
            is_active=symbol.is_active,
            created_at=symbol.created_at
        ) for symbol in symbols]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tracked symbols: {str(e)}")


@router.post("/tracked", response_model=TrackedSymbolResponse)
async def add_tracked_symbol(
    symbol: TrackedSymbolCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add new symbol to tracking"""
    try:
        # Check if symbol already exists
        result = await db.execute(select(TrackedSymbol).where(TrackedSymbol.symbol == symbol.symbol))
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing symbol
            existing.is_active = symbol.is_active
            await db.commit()
            await db.refresh(existing)
            return TrackedSymbolResponse(
                symbol=existing.symbol,
                is_active=existing.is_active,
                created_at=existing.created_at
            )
        
        # Create new symbol
        tracked_symbol = TrackedSymbol(
            symbol=symbol.symbol,
            is_active=symbol.is_active
        )
        
        db.add(tracked_symbol)
        await db.commit()
        await db.refresh(tracked_symbol)
        
        return TrackedSymbolResponse(
            symbol=tracked_symbol.symbol,
            is_active=tracked_symbol.is_active,
            created_at=tracked_symbol.created_at
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error adding tracked symbol: {str(e)}")


@router.put("/tracked/{symbol}", response_model=TrackedSymbolResponse)
async def update_tracked_symbol(
    symbol: str,
    update_data: TrackedSymbolUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update tracked symbol"""
    try:
        result = await db.execute(select(TrackedSymbol).where(TrackedSymbol.symbol == symbol))
        tracked_symbol = result.scalar_one_or_none()
        
        if not tracked_symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
        
        if update_data.is_active is not None:
            tracked_symbol.is_active = update_data.is_active
        
        await db.commit()
        await db.refresh(tracked_symbol)
        
        return TrackedSymbolResponse(
            symbol=tracked_symbol.symbol,
            is_active=tracked_symbol.is_active,
            created_at=tracked_symbol.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating tracked symbol: {str(e)}")


@router.delete("/tracked/{symbol}")
async def remove_tracked_symbol(
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """Remove symbol from tracking (set inactive)"""
    try:
        result = await db.execute(select(TrackedSymbol).where(TrackedSymbol.symbol == symbol))
        tracked_symbol = result.scalar_one_or_none()
        
        if not tracked_symbol:
            raise HTTPException(status_code=404, detail="Symbol not found")
        
        tracked_symbol.is_active = False
        await db.commit()
        
        return {"message": f"Symbol {symbol} removed from tracking"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error removing tracked symbol: {str(e)}")


@router.get("/crypto", response_model=List[CryptoSymbolResponse])
async def get_crypto_symbols(
    tradable_only: bool = Query(True, description="Show only tradable symbols"),
    db: AsyncSession = Depends(get_db)
):
    """Get cryptocurrency symbols database"""
    try:
        query = select(CryptoSymbol)
        if tradable_only:
            query = query.where(CryptoSymbol.is_tradable == True)
        
        result = await db.execute(query)
        symbols = result.scalars().all()
        
        return [CryptoSymbolResponse(
            id=symbol.id,
            symbol=symbol.symbol,
            name=symbol.name,
            description=symbol.description,
            is_tradable=symbol.is_tradable,
            last_updated=symbol.last_updated
        ) for symbol in symbols]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching crypto symbols: {str(e)}")


@router.post("/crypto", response_model=CryptoSymbolResponse)
async def add_crypto_symbol(
    symbol: CryptoSymbolCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add new cryptocurrency symbol to database"""
    try:
        # Check if symbol already exists
        result = await db.execute(select(CryptoSymbol).where(CryptoSymbol.symbol == symbol.symbol))
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(status_code=400, detail="Symbol already exists")
        
        crypto_symbol = CryptoSymbol(
            symbol=symbol.symbol,
            name=symbol.name,
            description=symbol.description,
            is_tradable=symbol.is_tradable
        )
        
        db.add(crypto_symbol)
        await db.commit()
        await db.refresh(crypto_symbol)
        
        return CryptoSymbolResponse(
            id=crypto_symbol.id,
            symbol=crypto_symbol.symbol,
            name=crypto_symbol.name,
            description=crypto_symbol.description,
            is_tradable=crypto_symbol.is_tradable,
            last_updated=crypto_symbol.last_updated
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error adding crypto symbol: {str(e)}")


@router.get("/prices", response_model=List[SymbolPrice])
async def get_symbol_prices(
    symbols: str = Query(..., description="Comma-separated list of symbols"),
    services: dict = Depends(lambda: None)
):
    """Get current prices for symbols"""
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        
        if not symbol_list:
            raise HTTPException(status_code=400, detail="No symbols provided")
        
        # This would use the price service in a real implementation
        # For now, return mock data
        from datetime import datetime
        return [
            SymbolPrice(
                symbol=symbol,
                price=50000.0 if symbol == "BTC" else 3000.0,
                timestamp=datetime.now()
            )
            for symbol in symbol_list
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching prices: {str(e)}")
