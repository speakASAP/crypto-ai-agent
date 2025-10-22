from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.models.alerts import PriceAlert, AlertHistory
from app.schemas.alerts import (
    PriceAlertCreate, 
    PriceAlertUpdate, 
    PriceAlertResponse, 
    AlertHistoryResponse
)
from app.services.cache_service import CacheService

router = APIRouter()


def get_cache_service() -> CacheService:
    """Dependency to get cache service"""
    return None


@router.get("/", response_model=List[PriceAlertResponse])
async def get_alerts(
    active_only: bool = Query(True, description="Show only active alerts"),
    db: AsyncSession = Depends(get_db)
):
    """Get all price alerts"""
    try:
        query = select(PriceAlert)
        if active_only:
            query = query.where(PriceAlert.is_active == True)
        
        result = await db.execute(query)
        alerts = result.scalars().all()
        
        return [PriceAlertResponse(
            id=alert.id,
            symbol=alert.symbol,
            alert_type=alert.alert_type,
            threshold_price=alert.threshold_price,
            message=alert.message,
            is_active=alert.is_active,
            created_at=alert.created_at,
            updated_at=alert.updated_at
        ) for alert in alerts]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching alerts: {str(e)}")


@router.post("/", response_model=PriceAlertResponse)
async def create_alert(
    alert: PriceAlertCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create new price alert"""
    try:
        price_alert = PriceAlert(
            symbol=alert.symbol,
            alert_type=alert.alert_type,
            threshold_price=alert.threshold_price,
            message=alert.message,
            is_active=alert.is_active
        )
        
        db.add(price_alert)
        await db.commit()
        await db.refresh(price_alert)
        
        return PriceAlertResponse(
            id=price_alert.id,
            symbol=price_alert.symbol,
            alert_type=price_alert.alert_type,
            threshold_price=price_alert.threshold_price,
            message=price_alert.message,
            is_active=price_alert.is_active,
            created_at=price_alert.created_at,
            updated_at=price_alert.updated_at
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating alert: {str(e)}")


@router.put("/{alert_id}", response_model=PriceAlertResponse)
async def update_alert(
    alert_id: int,
    alert: PriceAlertUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update price alert"""
    try:
        result = await db.execute(select(PriceAlert).where(PriceAlert.id == alert_id))
        price_alert = result.scalar_one_or_none()
        
        if not price_alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        update_data = alert.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(price_alert, field, value)
        
        await db.commit()
        await db.refresh(price_alert)
        
        return PriceAlertResponse(
            id=price_alert.id,
            symbol=price_alert.symbol,
            alert_type=price_alert.alert_type,
            threshold_price=price_alert.threshold_price,
            message=price_alert.message,
            is_active=price_alert.is_active,
            created_at=price_alert.created_at,
            updated_at=price_alert.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating alert: {str(e)}")


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete price alert"""
    try:
        result = await db.execute(select(PriceAlert).where(PriceAlert.id == alert_id))
        price_alert = result.scalar_one_or_none()
        
        if not price_alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        await db.execute(delete(PriceAlert).where(PriceAlert.id == alert_id))
        await db.commit()
        
        return {"message": "Alert deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting alert: {str(e)}")


@router.get("/history", response_model=List[AlertHistoryResponse])
async def get_alert_history(
    limit: int = Query(100, description="Number of history records to return"),
    db: AsyncSession = Depends(get_db)
):
    """Get alert trigger history"""
    try:
        result = await db.execute(
            select(AlertHistory)
            .order_by(AlertHistory.triggered_at.desc())
            .limit(limit)
        )
        history = result.scalars().all()
        
        return [AlertHistoryResponse(
            id=record.id,
            alert_id=record.alert_id,
            symbol=record.symbol,
            triggered_price=record.triggered_price,
            threshold_price=record.threshold_price,
            alert_type=record.alert_type,
            message=record.message,
            triggered_at=record.triggered_at
        ) for record in history]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching alert history: {str(e)}")


@router.post("/{alert_id}/trigger")
async def trigger_alert(
    alert_id: int,
    current_price: float,
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger an alert (for testing)"""
    try:
        result = await db.execute(select(PriceAlert).where(PriceAlert.id == alert_id))
        price_alert = result.scalar_one_or_none()
        
        if not price_alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Create history record
        history_record = AlertHistory(
            alert_id=price_alert.id,
            symbol=price_alert.symbol,
            triggered_price=current_price,
            threshold_price=price_alert.threshold_price,
            alert_type=price_alert.alert_type,
            message=price_alert.message
        )
        
        db.add(history_record)
        await db.commit()
        
        return {"message": "Alert triggered successfully", "alert_id": alert_id}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error triggering alert: {str(e)}")
