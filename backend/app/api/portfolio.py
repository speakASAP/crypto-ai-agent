from datetime import datetime
import asyncio
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies.auth import get_current_active_user, get_db_connection
from ..core.config import settings
from ..services.currency_service import currency_service
from ..schemas.portfolio import PortfolioItem, PortfolioCreate, PortfolioUpdate
from ..utils.db import normalize_placeholders as _normalize_placeholders, execute_insert_and_get_id as _execute_insert_and_get_id
from ..utils.logger import get_logger
from .ws import manager  # for potential broadcast references


router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
logger = get_logger("backend.app.api.portfolio")


def format_total_investment_text(total: float, base_currency: str) -> str:
    symbol = {
        "USD": "$",
        "EUR": "€",
        "CZK": "Kč",
        "GBP": "£",
        "JPY": "¥",
    }.get(base_currency, base_currency)
    return f"{symbol}{round(total, 2)}"


def convert_portfolio_item(item: dict, target_currency: str) -> dict:
    base_currency = item.get("base_currency", "USD")
    if target_currency == base_currency:
        return item
    # Convert displayed values; USD-based fields remain as-is
    rate = currency_service.get_rate(target_currency) / (currency_service.get_rate(base_currency) if base_currency != "USD" else 1)
    converted = dict(item)
    for key in ["current_value", "price_buy", "pnl", "commission"]:
        if converted.get(key) is not None:
            converted[key] = round(converted[key] * rate, 8)
    converted["base_currency"] = target_currency
    return converted


@router.get("/", response_model=List[PortfolioItem])
async def get_portfolio(currency: str = "USD", current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
    sql = _normalize_placeholders("SELECT * FROM portfolio_items WHERE user_id = ? ORDER BY created_at DESC", is_pg)
    cursor.execute(sql, (current_user["id"],))
    rows = cursor.fetchall()
    conn.close()

    items = []
    for row in rows:
        item = {
            "id": row[0],
            "user_id": row[1],
            "symbol": row[2],
            "amount": row[3],
            "price_buy": row[4],
            "purchase_date": str(row[5]) if row[5] is not None else None,
            "base_currency": row[6],
            "purchase_price_eur": row[7],
            "purchase_price_czk": row[8],
            "source": row[9],
            "commission": row[10],
            "total_investment_text": row[11],
            "created_at": str(row[12]) if row[12] is not None else None,
            "updated_at": str(row[13]) if row[13] is not None else None,
            "current_price": row[14],
            "current_value": row[15],
            "pnl": row[16],
            "pnl_percent": row[17],
            "price_buy_usd": row[18] if len(row) > 18 else None,
            "commission_usd": row[19] if len(row) > 19 else None,
            "current_price_usd": row[20] if len(row) > 20 else None,
            "current_value_usd": row[21] if len(row) > 21 else None,
            "pnl_usd": row[22] if len(row) > 22 else None,
            "pnl_percent_usd": row[23] if len(row) > 23 else None,
            "exchange_rate_at_purchase": row[24] if len(row) > 24 else None,
        }
        items.append(convert_portfolio_item(item, currency))
    return items


@router.get("/summary")
async def get_portfolio_summary(currency: str = "USD", current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
    sql = _normalize_placeholders("SELECT * FROM portfolio_items WHERE user_id = ?", is_pg)
    cursor.execute(sql, (current_user["id"],))
    rows = cursor.fetchall()
    conn.close()

    total_value = 0
    total_pnl = 0
    total_investment = 0

    for row in rows:
        item = {
            "base_currency": row[6],
            "current_value": row[15],
            "pnl": row[16],
            "amount": row[3],
            "price_buy": row[4],
            "commission": row[10],
        }
        converted_item = convert_portfolio_item(item, currency)
        total_value += converted_item["current_value"] or 0
        total_pnl += converted_item["pnl"] or 0
        total_investment += (converted_item["amount"] * converted_item["price_buy"] + converted_item["commission"])

    total_pnl_percent = (total_pnl / total_investment * 100) if total_investment > 0 else 0
    item_count = len(rows)
    return {
        "total_value": round(total_value, 8),
        "total_invested": round(total_investment, 8),
        "total_pnl": round(total_pnl, 8),
        "total_pnl_percent": round(total_pnl_percent, 8),
        "currency": currency,
        "item_count": item_count,
    }


@router.post("/", response_model=PortfolioItem)
async def create_portfolio_item(item: PortfolioCreate, current_user: dict = Depends(get_current_active_user)):
    if not isinstance(item.amount, (int, float)) or item.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be a positive number")
    if not isinstance(item.price_buy, (int, float)) or item.price_buy <= 0:
        raise HTTPException(status_code=400, detail="Price must be a positive number")
    if not isinstance(item.commission, (int, float)) or item.commission < 0:
        raise HTTPException(status_code=400, detail="Commission must be a non-negative number")

    conn = get_db_connection()
    cursor = conn.cursor()
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))

    now = datetime.now().isoformat() + "Z"
    exchange_rate = 1.0
    if item.base_currency != "USD":
        exchange_rate = currency_service.get_rate(item.base_currency)

    price_buy_usd = item.price_buy / exchange_rate if item.base_currency != "USD" else item.price_buy
    commission_usd = item.commission / exchange_rate if item.base_currency != "USD" else item.commission

    total_investment = (item.amount * item.price_buy) + item.commission
    formatted_total_investment = item.total_investment_text
    if not formatted_total_investment or not any(s in formatted_total_investment for s in ["$", "€", "Kč", "£", "¥"]):
        formatted_total_investment = format_total_investment_text(total_investment, item.base_currency)

    insert_sql = '''
        INSERT INTO portfolio_items 
        (user_id, symbol, amount, price_buy, purchase_date, base_currency, source, commission, 
         total_investment_text, created_at, updated_at, current_price, current_value, pnl, pnl_percent,
         price_buy_usd, commission_usd, current_price_usd, current_value_usd, pnl_usd, pnl_percent_usd,
         exchange_rate_at_purchase)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    params = (
        current_user["id"], item.symbol, item.amount, item.price_buy, item.purchase_date, item.base_currency,
        item.source, item.commission, formatted_total_investment, now, now,
        round(item.price_buy, 8), round(item.amount * item.price_buy, 8), 0.0, 0.0,
        round(price_buy_usd, 8), round(commission_usd, 8), round(price_buy_usd, 8),
        round(item.amount * price_buy_usd, 8), 0.0, 0.0, exchange_rate,
    )
    sql = _normalize_placeholders(insert_sql, is_pg)
    item_id = _execute_insert_and_get_id(cursor, sql, params, is_pg)
    conn.commit()
    conn.close()

    # Immediately fetch prices for the newly added symbol
    try:
        from ..main import fetch_prices_for_symbols
        logger.info(f"🔄 Fetching prices for newly added symbol: {item.symbol}")
        await fetch_prices_for_symbols([item.symbol])
        logger.info(f"✅ Price update completed for {item.symbol}")
    except Exception as e:
        logger.error(f"⚠️ Failed to fetch prices for {item.symbol}: {e}", exc_info=True)
        # Don't fail the creation if price fetch fails

    return PortfolioItem(
        id=item_id,
        symbol=item.symbol,
        amount=item.amount,
        price_buy=item.price_buy,
        purchase_date=item.purchase_date,
        base_currency=item.base_currency,
        source=item.source,
        commission=item.commission,
        total_investment_text=formatted_total_investment,
        created_at=now,
        updated_at=now,
        current_price=round(item.price_buy, 8),
        current_value=round(item.amount * item.price_buy, 8),
        pnl=0.0,
        pnl_percent=0.0,
        price_buy_usd=round(price_buy_usd, 8),
        commission_usd=round(commission_usd, 8),
        current_price_usd=round(price_buy_usd, 8),
        current_value_usd=round(item.amount * price_buy_usd, 8),
        pnl_usd=0.0,
        pnl_percent_usd=0.0,
        exchange_rate_at_purchase=exchange_rate,
    )


@router.put("/{item_id}", response_model=PortfolioItem)
async def update_portfolio_item(item_id: int, item: PortfolioUpdate, current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
    sql_sel = _normalize_placeholders("SELECT * FROM portfolio_items WHERE id = ? AND user_id = ?", is_pg)
    cursor.execute(sql_sel, (item_id, current_user["id"]))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Portfolio item not found")

    update_fields = []
    update_values = []
    if item.symbol is not None:
        update_fields.append("symbol = ?")
        update_values.append(item.symbol)
    if item.amount is not None:
        update_fields.append("amount = ?")
        update_values.append(item.amount)
    if item.price_buy is not None:
        update_fields.append("price_buy = ?")
        update_values.append(item.price_buy)
    if item.purchase_date is not None:
        update_fields.append("purchase_date = ?")
        update_values.append(item.purchase_date)
    if item.base_currency is not None:
        update_fields.append("base_currency = ?")
        update_values.append(item.base_currency)
    if item.source is not None:
        update_fields.append("source = ?")
        update_values.append(item.source)
    if item.commission is not None:
        update_fields.append("commission = ?")
        update_values.append(item.commission)
    if item.total_investment_text is not None:
        update_fields.append("total_investment_text = ?")
        update_values.append(item.total_investment_text)

    if update_fields:
        # Special-case formatting and USD recalcs
        if "total_investment_text" in [f.split(" = ")[0] for f in update_fields]:
            total_investment_text_idx = next((i for i, f in enumerate(update_fields) if f.startswith("total_investment_text = ?")), None)
            if total_investment_text_idx is not None:
                total_investment_text = update_values[total_investment_text_idx]
                if not total_investment_text or not any(s in total_investment_text for s in ["$", "€", "Kč", "£", "¥"]):
                    sql_sel_cur = _normalize_placeholders("SELECT amount, price_buy, commission, base_currency FROM portfolio_items WHERE id = ?", is_pg)
                    cursor.execute(sql_sel_cur, (item_id,))
                    current_data = cursor.fetchone()
                    if current_data:
                        amount, price_buy, commission, base_currency = current_data
                        total_investment = (amount * price_buy) + commission
                        update_values[total_investment_text_idx] = format_total_investment_text(total_investment, base_currency)

        needs_usd_recalc = any(f in update_fields for f in ["price_buy = ?", "amount = ?", "commission = ?", "base_currency = ?"])
        if needs_usd_recalc:
            sql_sel_old = _normalize_placeholders("SELECT amount, price_buy, commission, base_currency FROM portfolio_items WHERE id = ?", is_pg)
            cursor.execute(sql_sel_old, (item_id,))
            old_data = cursor.fetchone()
            update_fields.append("updated_at = ?")
            update_values.append(datetime.now().isoformat() + "Z")
            update_values.append(item_id)
            dyn_sql = f"""
                UPDATE portfolio_items 
                SET {', '.join(update_fields)}
                WHERE id = ?
            """
            sql_upd = _normalize_placeholders(dyn_sql, is_pg)
            cursor.execute(sql_upd, update_values)
            conn.commit()

            sql_sel_new = _normalize_placeholders("SELECT amount, price_buy, commission, base_currency FROM portfolio_items WHERE id = ?", is_pg)
            cursor.execute(sql_sel_new, (item_id,))
            new_data = cursor.fetchone()
            if new_data:
                amount, price_buy, commission, base_currency = new_data
                exchange_rate = 1.0 if base_currency == "USD" else currency_service.get_rate(base_currency)
                price_buy_usd = price_buy / exchange_rate if base_currency != "USD" else price_buy
                commission_usd = commission / exchange_rate if base_currency != "USD" else commission
                upd_sql2 = '''
                    UPDATE portfolio_items 
                    SET price_buy_usd = ?, commission_usd = ?, exchange_rate_at_purchase = ?,
                        current_value = ?, current_value_usd = ?, pnl = ?, pnl_percent = ?, pnl_usd = ?, pnl_percent_usd = ?
                    WHERE id = ?
                '''
                upd_sql2 = _normalize_placeholders(upd_sql2, is_pg)
                cursor.execute(
                    upd_sql2,
                    (
                        round(price_buy_usd, 8), round(commission_usd, 8), exchange_rate,
                        round(amount * price_buy, 8), round(amount * price_buy_usd, 8),
                        0.0, 0.0, 0.0, 0.0, item_id,
                    ),
                )
                conn.commit()

                try:
                    from ..main import fetch_prices_for_symbols  # lazy import to avoid cycles
                    asyncio.create_task(fetch_prices_for_symbols([row[2] if old_data else ""]))
                except Exception:
                    pass
        else:
            update_fields.append("updated_at = ?")
            update_values.append(datetime.now().isoformat() + "Z")
            update_values.append(item_id)
            dyn_sql2 = f"""
                UPDATE portfolio_items 
                SET {', '.join(update_fields)}
                WHERE id = ?
            """
            sql_upd2 = _normalize_placeholders(dyn_sql2, is_pg)
            cursor.execute(sql_upd2, update_values)
            conn.commit()

    conn.close()

    conn = get_db_connection()
    cursor = conn.cursor()
    sql_sel_final = _normalize_placeholders("SELECT * FROM portfolio_items WHERE id = ?", is_pg)
    cursor.execute(sql_sel_final, (item_id,))
    row = cursor.fetchone()
    conn.close()

    return PortfolioItem(
        id=row[0], symbol=row[2], amount=row[3], price_buy=row[4],
        purchase_date=str(row[5]) if row[5] is not None else None, base_currency=row[6], purchase_price_eur=row[7],
        purchase_price_czk=row[8], source=row[9], commission=row[10],
        total_investment_text=row[11], created_at=str(row[12]) if row[12] is not None else None, updated_at=str(row[13]) if row[13] is not None else None,
        current_price=row[14], current_value=row[15], pnl=row[16], pnl_percent=row[17],
        price_buy_usd=row[18] if len(row) > 18 else None,
        commission_usd=row[19] if len(row) > 19 else None,
        current_price_usd=row[20] if len(row) > 20 else None,
        current_value_usd=row[21] if len(row) > 21 else None,
        pnl_usd=row[22] if len(row) > 22 else None,
        pnl_percent_usd=row[23] if len(row) > 23 else None,
        exchange_rate_at_purchase=row[24] if len(row) > 24 else None,
    )


@router.delete("/{item_id}")
async def delete_portfolio_item(item_id: int, current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
    sql_del = _normalize_placeholders("DELETE FROM portfolio_items WHERE id = ? AND user_id = ?", is_pg)
    cursor.execute(sql_del, (item_id, current_user["id"]))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    return {"message": "Portfolio item deleted successfully"}


