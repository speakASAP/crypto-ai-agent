from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies.auth import get_current_active_user, get_db_connection
from ..services.currency_service import currency_service
from ..utils.logger import get_logger
from ..utils.db import normalize_placeholders as _normalize_placeholders, is_postgres_connection


router = APIRouter(prefix="/api/import", tags=["exchange-imports"])
logger = get_logger("backend.app.api.exchange_imports")


@router.post("/binance/test-connection")
async def test_binance_connection(current_user: dict = Depends(get_current_active_user)):
    try:
        from ..services.binance_credential_service import binance_credential_service
        result = await binance_credential_service.test_user_credentials(current_user["id"])
        return result
    except Exception as e:
        logger.error(f"Error testing Binance connection: {e}")
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")


@router.post("/binance/preview")
async def preview_binance_import(current_user: dict = Depends(get_current_active_user)):
    try:
        from ..services.binance_credential_service import binance_credential_service
        result = await binance_credential_service.import_user_portfolio(current_user["id"])
        return result
    except Exception as e:
        logger.error(f"Error previewing Binance import: {e}")
        raise HTTPException(status_code=500, detail=f"Import preview failed: {str(e)}")


@router.post("/binance/execute")
async def execute_binance_import(current_user: dict = Depends(get_current_active_user)):
    try:
        from ..services.binance_credential_service import binance_credential_service
        result = await binance_credential_service.import_user_portfolio(current_user["id"])
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['message'])
        conn = get_db_connection()
        cursor = conn.cursor()
        is_pg = is_postgres_connection(conn)
        imported_count = 0
        now = datetime.now().isoformat() + "Z"

        for item in result['portfolio_items']:
            try:
                check_duplicate_sql = _normalize_placeholders(
                    "SELECT id FROM portfolio_items WHERE user_id = ? AND symbol = ? AND ABS(amount - ?) < 0.001",
                    is_pg
                )
                cursor.execute(check_duplicate_sql, (current_user["id"], item['symbol'], item['amount']))
                if cursor.fetchone():
                    logger.info(f"Skipping duplicate item: {item['symbol']}")
                    continue
                currency_service.ensure_rates_initialized()
                base_currency = item.get('base_currency', 'USD')
                price_buy = item['price_buy']
                commission = item.get('commission', 0.0)
                if base_currency != 'USD' and price_buy > 0:
                    price_buy_usd = currency_service.convert_amount(price_buy, base_currency, 'USD')
                    commission_usd = currency_service.convert_amount(commission, base_currency, 'USD')
                    exchange_rate = currency_service.rates.get(base_currency, 1.0) if base_currency in currency_service.rates else 1.0
                else:
                    price_buy_usd = price_buy
                    commission_usd = commission
                    exchange_rate = None
                
                insert_sql = _normalize_placeholders(
                    "INSERT INTO portfolio_items "
                    "(user_id, symbol, amount, price_buy, purchase_date, base_currency, source, commission, "
                    "total_investment_text, created_at, updated_at, current_price, current_value, pnl, pnl_percent, "
                    "price_buy_usd, commission_usd, exchange_rate_at_purchase) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    is_pg
                )
                cursor.execute(insert_sql, (
                    current_user["id"], item['symbol'], item['amount'], price_buy,
                    item['purchase_date'], base_currency, item['source'], commission,
                    item['total_investment_text'], now, now,
                    round(price_buy, 8), round(item['amount'] * price_buy, 8), 0.0, 0.0,
                    round(price_buy_usd, 8), round(commission_usd, 8), exchange_rate
                ))
                imported_count += 1
            except Exception as e:
                logger.warning(f"Failed to import item {item['symbol']}: {e}")
                continue

        history_sql = _normalize_placeholders(
            "INSERT INTO import_history "
            "(user_id, source, import_date, items_imported, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            is_pg
        )
        cursor.execute(history_sql, (current_user["id"], 'binance', now, imported_count, 'success' if imported_count > 0 else 'partial', now))
        conn.commit()
        conn.close()
        logger.info(f"✅ Binance import completed: {imported_count} items imported for user {current_user['id']}")
        return {
            'success': True,
            'message': f'Successfully imported {imported_count} portfolio items from Binance',
            'items_imported': imported_count,
            'total_found': len(result['portfolio_items'])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing Binance import: {e}")
        raise HTTPException(status_code=500, detail=f"Import execution failed: {str(e)}")


@router.post("/bitfinex/test-connection")
async def test_bitfinex_import_connection(current_user: dict = Depends(get_current_active_user)):
    try:
        from ..services.bitfinex_credential_service import bitfinex_credential_service
        result = await bitfinex_credential_service.test_user_credentials(current_user["id"])
        return result
    except Exception as e:
        logger.error(f"Error testing Bitfinex connection: {e}")
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")


@router.post("/bitfinex/preview")
async def preview_bitfinex_import(current_user: dict = Depends(get_current_active_user)):
    try:
        from ..services.bitfinex_credential_service import bitfinex_credential_service
        result = await bitfinex_credential_service.import_user_portfolio(current_user["id"])
        return result
    except Exception as e:
        logger.error(f"Error previewing Bitfinex import: {e}")
        raise HTTPException(status_code=500, detail=f"Import preview failed: {str(e)}")


@router.post("/bitfinex/execute")
async def execute_bitfinex_import(current_user: dict = Depends(get_current_active_user)):
    try:
        from ..services.bitfinex_credential_service import bitfinex_credential_service
        result = await bitfinex_credential_service.import_user_portfolio(current_user["id"])
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['message'])
        conn = get_db_connection()
        cursor = conn.cursor()
        is_pg = is_postgres_connection(conn)
        imported_count = 0
        now = datetime.now().isoformat() + "Z"

        for item in result['portfolio_items']:
            try:
                check_duplicate_sql = _normalize_placeholders(
                    "SELECT id FROM portfolio_items WHERE user_id = ? AND symbol = ? AND ABS(amount - ?) < 0.001",
                    is_pg
                )
                cursor.execute(check_duplicate_sql, (current_user["id"], item['symbol'], item['amount']))
                if cursor.fetchone():
                    logger.info(f"Skipping duplicate item: {item['symbol']}")
                    continue
                currency_service.ensure_rates_initialized()
                base_currency = item.get('base_currency', 'USD')
                price_buy = item['price_buy']
                commission = item.get('commission', 0.0)
                if base_currency != 'USD' and price_buy > 0:
                    price_buy_usd = currency_service.convert_amount(price_buy, base_currency, 'USD')
                    commission_usd = currency_service.convert_amount(commission, base_currency, 'USD')
                    exchange_rate = currency_service.rates.get(base_currency, 1.0) if base_currency in currency_service.rates else 1.0
                else:
                    price_buy_usd = price_buy
                    commission_usd = commission
                    exchange_rate = None
                
                insert_sql = _normalize_placeholders(
                    "INSERT INTO portfolio_items "
                    "(user_id, symbol, amount, price_buy, purchase_date, base_currency, source, commission, "
                    "total_investment_text, created_at, updated_at, current_price, current_value, pnl, pnl_percent, "
                    "price_buy_usd, commission_usd, exchange_rate_at_purchase) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    is_pg
                )
                cursor.execute(insert_sql, (
                    current_user["id"], item['symbol'], item['amount'], price_buy,
                    item['purchase_date'], base_currency, item['source'], commission,
                    item['total_investment_text'], now, now,
                    round(price_buy, 8), round(item['amount'] * price_buy, 8), 0.0, 0.0,
                    round(price_buy_usd, 8), round(commission_usd, 8), exchange_rate
                ))
                imported_count += 1
            except Exception as e:
                logger.warning(f"Failed to import item {item['symbol']}: {e}")
                continue

        history_sql = _normalize_placeholders(
            "INSERT INTO import_history "
            "(user_id, source, import_date, items_imported, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            is_pg
        )
        cursor.execute(history_sql, (current_user["id"], 'Bitfinex', now, imported_count, 'success' if imported_count > 0 else 'partial', now))
        conn.commit()
        conn.close()
        logger.info(f"✅ Bitfinex import completed: {imported_count} items imported for user {current_user['id']}")
        return {
            'success': True,
            'message': f'Successfully imported {imported_count} portfolio items from Bitfinex',
            'items_imported': imported_count,
            'total_found': len(result['portfolio_items'])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing Bitfinex import: {e}")
        raise HTTPException(status_code=500, detail=f"Import execution failed: {str(e)}")


@router.get("/history")
async def get_import_history(current_user: dict = Depends(get_current_active_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_pg = is_postgres_connection(conn)
        history_sql = _normalize_placeholders(
            "SELECT source, import_date, items_imported, status, error_message, created_at "
            "FROM import_history WHERE user_id = ? ORDER BY created_at DESC",
            is_pg
        )
        cursor.execute(history_sql, (current_user["id"],))
        rows = cursor.fetchall()
        conn.close()
        history = []
        for row in rows:
            history.append({
                'source': row[0],
                'import_date': row[1],
                'items_imported': row[2],
                'status': row[3],
                'error_message': row[4],
                'created_at': row[5]
            })
        return {'import_history': history}
    except Exception as e:
        logger.error(f"Error getting import history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get import history: {str(e)}")

