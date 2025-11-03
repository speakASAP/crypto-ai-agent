from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies.auth import get_current_active_user, get_db_connection
from ..core.config import settings
from ..services.currency_service import currency_service
from ..schemas.alerts import PriceAlert, PriceAlertCreate, PriceAlertUpdate
from ..utils.db import normalize_placeholders as _normalize_placeholders, execute_insert_and_get_id as _execute_insert_and_get_id
try:
    from utils.logger import get_logger
except Exception:  # pragma: no cover
    from ..utils.logger import get_logger


router = APIRouter(prefix="/api/alerts", tags=["alerts"])
logger = get_logger("backend.app.api.alerts")


@router.get("/", response_model=List[PriceAlert])
async def get_alerts(active_only: bool = False, current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()

    base_select = "SELECT id, user_id, symbol, threshold_price, alert_type, message, is_active, created_at FROM alerts"
    if active_only:
        sql = base_select + " WHERE user_id = %s AND is_active = %s ORDER BY created_at DESC"
        sql = _normalize_placeholders(sql)
        params = (current_user["id"], True)
        cursor.execute(sql, params)
    else:
        sql = base_select + " WHERE user_id = %s ORDER BY created_at DESC"
        sql = _normalize_placeholders(sql)
        params = (current_user["id"],)
        cursor.execute(sql, params)

    rows = cursor.fetchall()
    conn.close()

    alerts: List[PriceAlert] = []
    for row in rows:
        created_at_val = row[7].isoformat() if hasattr(row[7], 'isoformat') else row[7]
        alerts.append(PriceAlert(
            id=row[0], symbol=row[2], threshold_price=row[3],
            alert_type=row[4], message=row[5], is_active=bool(row[6]),
            created_at=created_at_val, threshold_price_usd=None,
            base_currency=None, exchange_rate_at_creation=None,
        ))
    return alerts


@router.post("/", response_model=PriceAlert)
async def create_alert(alert: PriceAlertCreate, current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat() + "Z"
    base_currency = alert.base_currency or "USD"
    exchange_rate = 1.0 if base_currency == "USD" else currency_service.get_rate(base_currency)
    threshold_price_usd = alert.threshold_price / exchange_rate if base_currency != "USD" else alert.threshold_price

    insert_sql = '''
        INSERT INTO alerts (user_id, symbol, threshold_price, alert_type, message, is_active, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    '''
    params = (current_user["id"], alert.symbol, alert.threshold_price, alert.alert_type, alert.message, True, now)
    sql = _normalize_placeholders(insert_sql)
    alert_id = _execute_insert_and_get_id(cursor, sql, params)
    conn.commit()
    conn.close()

    return PriceAlert(
        id=alert_id, symbol=alert.symbol, threshold_price=alert.threshold_price,
        alert_type=alert.alert_type, message=alert.message, is_active=True,
        created_at=now, threshold_price_usd=threshold_price_usd,
        base_currency=base_currency, exchange_rate_at_creation=exchange_rate,
    )


@router.put("/{alert_id}", response_model=PriceAlert)
async def update_alert(alert_id: int, alert: PriceAlertUpdate, current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql_sel = _normalize_placeholders("SELECT * FROM alerts WHERE id = %s AND user_id = %s")
    cursor.execute(sql_sel, (alert_id, current_user["id"]))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Alert not found")

    update_fields = []
    update_values = []
    if alert.symbol is not None:
        update_fields.append("symbol = %s")
        update_values.append(alert.symbol)
    if alert.threshold_price is not None:
        update_fields.append("threshold_price = %s")
        update_values.append(alert.threshold_price)
    if alert.alert_type is not None:
        update_fields.append("alert_type = %s")
        update_values.append(alert.alert_type)
    if alert.message is not None:
        update_fields.append("message = %s")
        update_values.append(alert.message)
    if alert.is_active is not None:
        update_fields.append("is_active = %s")
        update_values.append(alert.is_active)

    if update_fields:
        update_values.append(alert_id)
        dyn_sql = f"""
            UPDATE alerts 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        sql_upd = _normalize_placeholders(dyn_sql)
        cursor.execute(sql_upd, update_values)
        conn.commit()

    conn.close()

    conn = get_db_connection()
    cursor = conn.cursor()
    sql_sel2 = _normalize_placeholders("SELECT * FROM alerts WHERE id = %s")
    cursor.execute(sql_sel2, (alert_id,))
    row = cursor.fetchone()
    conn.close()

    return PriceAlert(
        id=row[0], symbol=row[2], threshold_price=row[3],
        alert_type=row[4], message=row[5], is_active=bool(row[6]),
        created_at=row[7],
    )


@router.delete("/{alert_id}")
async def delete_alert(alert_id: int, current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql_del = _normalize_placeholders("DELETE FROM alerts WHERE id = %s AND user_id = %s")
    cursor.execute(sql_del, (alert_id, current_user["id"]))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert deleted successfully"}


@router.get("/history")
async def get_alert_history(limit: int = 100, current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # PostgreSQL: join with alerts table to get symbol
        history_sql = """
            SELECT 
                ah.id,
                ah.alert_id,
                a.symbol,
                ah.triggered_price,
                ah.triggered_at
            FROM alert_history ah
            JOIN alerts a ON ah.alert_id = a.id
            WHERE ah.user_id = %s
            ORDER BY ah.triggered_at DESC
            LIMIT %s
        """
        cursor.execute(history_sql, (current_user["id"], limit))
        history = []
        for row in cursor.fetchall():
            history.append({
                "id": row[0],
                "alert_id": row[1],
                "symbol": row[2],
                "triggered_price": row[3],
                "triggered_at": row[4],
            })
        return history
    except Exception as e:
        logger.error(f"Error fetching alert history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch alert history")
    finally:
        conn.close()


