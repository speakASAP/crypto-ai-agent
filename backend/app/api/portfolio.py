from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from typing import List, Optional
from decimal import Decimal

from app.core.database import get_db
from app.models.portfolio import Portfolio
from app.schemas.portfolio import (
    PortfolioCreate, 
    PortfolioUpdate, 
    PortfolioResponse, 
    PortfolioSummary
)
from app.services.cache_service import CacheService
from app.services.currency_service import CurrencyService
from app.services.price_service import PriceService

router = APIRouter()


def get_cache_service() -> CacheService:
    """Dependency to get cache service"""
    # This will be injected by the main app
    return None


async def get_portfolio_service(
    db: AsyncSession = Depends(get_db),
    cache: CacheService = Depends(get_cache_service)
):
    """Dependency to get portfolio service"""
    currency_service = CurrencyService(cache)
    price_service = PriceService(cache)
    return {
        'db': db,
        'cache': cache,
        'currency_service': currency_service,
        'price_service': price_service
    }


@router.get("/", response_model=List[PortfolioResponse])
async def get_portfolio(
    currency: str = Query("USD", description="Display currency"),
    services: dict = Depends(get_portfolio_service)
):
    """Get portfolio with current prices and metrics"""
    try:
        # Get portfolio items from database
        result = await services['db'].execute(select(Portfolio))
        portfolio_items = result.scalars().all()
        
        if not portfolio_items:
            return []
        
        # Get current prices
        symbols = [item.symbol for item in portfolio_items]
        current_prices = await services['price_service'].get_current_prices(symbols)
        
        # Convert to response format
        portfolio_data = []
        for item in portfolio_items:
            current_price = current_prices.get(item.symbol, 0)
            
            # Convert prices to target currency
            if item.base_currency != currency:
                converted_price = await services['currency_service'].convert_currency(
                    item.price_buy, item.base_currency, currency
                )
            else:
                converted_price = item.price_buy
            
            # Calculate metrics
            current_value = Decimal(str(current_price)) * item.amount if current_price else Decimal('0')
            cost_basis = converted_price * item.amount
            pnl = current_value - cost_basis
            pnl_percent = (pnl / cost_basis * 100) if cost_basis > 0 else Decimal('0')
            
            portfolio_data.append(PortfolioResponse(
                id=item.id,
                symbol=item.symbol,
                amount=item.amount,
                price_buy=item.price_buy,
                purchase_date=item.purchase_date,
                base_currency=item.base_currency,
                purchase_price_eur=item.purchase_price_eur,
                purchase_price_czk=item.purchase_price_czk,
                source=item.source,
                commission=item.commission,
                created_at=item.created_at,
                updated_at=item.updated_at,
                current_price=Decimal(str(current_price)) if current_price else None,
                current_value=current_value,
                pnl=pnl,
                pnl_percent=pnl_percent
            ))
        
        return portfolio_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching portfolio: {str(e)}")


@router.post("/", response_model=PortfolioResponse)
async def create_portfolio_item(
    item: PortfolioCreate,
    services: dict = Depends(get_portfolio_service)
):
    """Add new item to portfolio"""
    try:
        # Convert prices to EUR and CZK for storage
        eur_price = await services['currency_service'].convert_currency(
            item.price_buy, item.base_currency, 'EUR'
        )
        czk_price = await services['currency_service'].convert_currency(
            item.price_buy, item.base_currency, 'CZK'
        )
        
        # Create portfolio item
        portfolio_item = Portfolio(
            symbol=item.symbol,
            amount=item.amount,
            price_buy=item.price_buy,
            purchase_date=item.purchase_date,
            base_currency=item.base_currency,
            purchase_price_eur=eur_price,
            purchase_price_czk=czk_price,
            source=item.source,
            commission=item.commission
        )
        
        services['db'].add(portfolio_item)
        await services['db'].commit()
        await services['db'].refresh(portfolio_item)
        
        # Invalidate portfolio cache
        await services['cache'].invalidate_pattern("portfolio:*")
        
        return PortfolioResponse(
            id=portfolio_item.id,
            symbol=portfolio_item.symbol,
            amount=portfolio_item.amount,
            price_buy=portfolio_item.price_buy,
            purchase_date=portfolio_item.purchase_date,
            base_currency=portfolio_item.base_currency,
            purchase_price_eur=portfolio_item.purchase_price_eur,
            purchase_price_czk=portfolio_item.purchase_price_czk,
            source=portfolio_item.source,
            commission=portfolio_item.commission,
            created_at=portfolio_item.created_at,
            updated_at=portfolio_item.updated_at
        )
        
    except Exception as e:
        await services['db'].rollback()
        raise HTTPException(status_code=500, detail=f"Error creating portfolio item: {str(e)}")


@router.put("/{item_id}", response_model=PortfolioResponse)
async def update_portfolio_item(
    item_id: int,
    item: PortfolioUpdate,
    services: dict = Depends(get_portfolio_service)
):
    """Update portfolio item"""
    try:
        # Get existing item
        result = await services['db'].execute(select(Portfolio).where(Portfolio.id == item_id))
        portfolio_item = result.scalar_one_or_none()
        
        if not portfolio_item:
            raise HTTPException(status_code=404, detail="Portfolio item not found")
        
        # Update fields
        update_data = item.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(portfolio_item, field, value)
        
        # Recalculate EUR and CZK prices if price_buy or base_currency changed
        if 'price_buy' in update_data or 'base_currency' in update_data:
            portfolio_item.purchase_price_eur = await services['currency_service'].convert_currency(
                portfolio_item.price_buy, portfolio_item.base_currency, 'EUR'
            )
            portfolio_item.purchase_price_czk = await services['currency_service'].convert_currency(
                portfolio_item.price_buy, portfolio_item.base_currency, 'CZK'
            )
        
        await services['db'].commit()
        await services['db'].refresh(portfolio_item)
        
        # Invalidate portfolio cache
        await services['cache'].invalidate_pattern("portfolio:*")
        
        return PortfolioResponse(
            id=portfolio_item.id,
            symbol=portfolio_item.symbol,
            amount=portfolio_item.amount,
            price_buy=portfolio_item.price_buy,
            purchase_date=portfolio_item.purchase_date,
            base_currency=portfolio_item.base_currency,
            purchase_price_eur=portfolio_item.purchase_price_eur,
            purchase_price_czk=portfolio_item.purchase_price_czk,
            source=portfolio_item.source,
            commission=portfolio_item.commission,
            created_at=portfolio_item.created_at,
            updated_at=portfolio_item.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await services['db'].rollback()
        raise HTTPException(status_code=500, detail=f"Error updating portfolio item: {str(e)}")


@router.delete("/{item_id}")
async def delete_portfolio_item(
    item_id: int,
    services: dict = Depends(get_portfolio_service)
):
    """Delete portfolio item"""
    try:
        result = await services['db'].execute(select(Portfolio).where(Portfolio.id == item_id))
        portfolio_item = result.scalar_one_or_none()
        
        if not portfolio_item:
            raise HTTPException(status_code=404, detail="Portfolio item not found")
        
        await services['db'].execute(delete(Portfolio).where(Portfolio.id == item_id))
        await services['db'].commit()
        
        # Invalidate portfolio cache
        await services['cache'].invalidate_pattern("portfolio:*")
        
        return {"message": "Portfolio item deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await services['db'].rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting portfolio item: {str(e)}")


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(
    currency: str = Query("USD", description="Display currency"),
    services: dict = Depends(get_portfolio_service)
):
    """Get portfolio summary with total value and P&L"""
    try:
        # Get portfolio items
        result = await services['db'].execute(select(Portfolio))
        portfolio_items = result.scalars().all()
        
        if not portfolio_items:
            return PortfolioSummary(
                total_value=Decimal('0'),
                total_pnl=Decimal('0'),
                total_pnl_percent=Decimal('0'),
                currency=currency,
                item_count=0
            )
        
        # Convert to dict format for currency service
        items_data = [
            {
                'symbol': item.symbol,
                'amount': float(item.amount),
                'price_buy': float(item.price_buy),
                'base_currency': item.base_currency
            }
            for item in portfolio_items
        ]
        
        # Calculate portfolio value
        portfolio_value = await services['currency_service'].get_portfolio_value(items_data, currency)
        
        return PortfolioSummary(
            total_value=portfolio_value['total_value'],
            total_pnl=portfolio_value['total_pnl'],
            total_pnl_percent=portfolio_value['total_pnl_percent'],
            currency=currency,
            item_count=len(portfolio_items)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating portfolio summary: {str(e)}")
