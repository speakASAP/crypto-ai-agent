from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies.auth import get_current_active_user, get_db_connection
from ..services.currency_service import currency_service
from ..utils.logger import get_logger
from ..utils.db import normalize_placeholders as _normalize_placeholders


router = APIRouter(prefix="/api/import", tags=["exchange-imports"])
logger = get_logger("backend.app.api.exchange_imports")


async def generate_predictions_for_symbols(symbols: list[str]) -> None:
    """Generate AI predictions for symbols that don't have them yet (non-blocking)"""
    if not symbols:
        return

    try:
        from ..services.ai_advisor_service import ai_advisor_service

        # Get unique symbols (uppercase)
        unique_symbols = list(set(s.upper() for s in symbols if s))

        if not unique_symbols:
            return

        # Check which symbols need predictions
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build IN clause with placeholders
        placeholders = ','.join(['%s'] * len(unique_symbols))
        check_sql = _normalize_placeholders(
            f"SELECT symbol FROM ai_predictions WHERE symbol IN ({placeholders}) AND user_id IS NULL"
        )
        cursor.execute(check_sql, unique_symbols)
        existing_symbols = {row[0] for row in cursor.fetchall()}
        conn.close()

        # Generate predictions for symbols that don't have them
        symbols_to_generate = [s for s in unique_symbols if s not in existing_symbols]

        if not symbols_to_generate:
            logger.debug(f"All {len(unique_symbols)} imported symbols already have predictions")
            return

        logger.info(f"🤖 Generating AI predictions for {len(symbols_to_generate)} imported symbols: {symbols_to_generate[:10]}{'...' if len(symbols_to_generate) > 10 else ''}")

        # Generate predictions for each symbol (non-blocking, failures don't stop the import)
        for symbol in symbols_to_generate:
            try:
                predictions = await ai_advisor_service.generate_predictions(
                    user_id=None,  # None = global predictions (stored with user_id = NULL)
                    symbol=symbol,
                    force_regenerate=True,  # Force generation for newly imported symbols
                )
                if predictions:
                    logger.info(f"✅ AI predictions generated for {symbol}")
                else:
                    logger.warning(f"⚠️ No predictions generated for {symbol} (may be rate-limited or symbol not supported)")
            except Exception as e:
                logger.error(f"⚠️ Failed to generate predictions for {symbol}: {e}", exc_info=True)
                # Continue with other symbols even if one fails
                continue

    except Exception as e:
        logger.error(f"⚠️ Error in prediction generation helper: {e}", exc_info=True)
        # Don't fail the import if prediction generation fails


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
        imported_count = 0
        now = datetime.now().isoformat() + "Z"
        items_with_missing_data = []

        for item in result['portfolio_items']:
            try:
                # Normalize symbol for checking (TRON -> TRX, case-insensitive)
                symbol = item['symbol'].upper()
                if symbol == 'TRON':
                    symbol = 'TRX'
                
                source = item.get('source', 'Binance')
                
                # Check if exact duplicate exists (same symbol, same amount, same source)
                # This allows same symbol from different sources (Revolut, Binance, Bitfinex)
                check_duplicate_sql = _normalize_placeholders(
                    "SELECT id FROM portfolio_items WHERE user_id = %s AND UPPER(symbol) = UPPER(%s) AND source = %s AND ABS(amount - %s) < 0.001"
                )
                cursor.execute(check_duplicate_sql, (current_user["id"], symbol, source, item['amount']))
                if cursor.fetchone():
                    logger.info(f"Skipping duplicate item: {symbol} from {source} (same amount: {item['amount']})")
                    continue
                
                currency_service.ensure_rates_initialized()
                base_currency = item.get('base_currency', 'USD')
                price_buy = item['price_buy']
                commission = item.get('commission', 0.0)
                purchase_date = item.get('purchase_date')
                
                # Check for missing data
                missing_fields = []
                if not price_buy or price_buy == 0:
                    missing_fields.append('Buy Price')
                if not purchase_date or purchase_date == '' or purchase_date == 'Unknown':
                    missing_fields.append('Purchase Date')
                
                # Track items with missing data
                if missing_fields:
                    items_with_missing_data.append({
                        'symbol': symbol,
                        'missing_fields': missing_fields,
                        'amount': item['amount']
                    })
                
                if base_currency != 'USD' and price_buy > 0:
                    price_buy_usd = currency_service.convert_amount(price_buy, base_currency, 'USD')
                    commission_usd = currency_service.convert_amount(commission, base_currency, 'USD')
                    exchange_rate = currency_service.rates.get(base_currency, 1.0) if base_currency in currency_service.rates else 1.0
                else:
                    price_buy_usd = price_buy
                    commission_usd = commission
                    exchange_rate = None
                
                # New item - insert it (same symbol from different sources are allowed)
                insert_sql = _normalize_placeholders(
                    "INSERT INTO portfolio_items "
                    "(user_id, symbol, amount, price_buy, purchase_date, base_currency, source, commission, "
                    "total_investment_text, created_at, updated_at, current_price, current_value, pnl, pnl_percent, "
                    "price_buy_usd, commission_usd, exchange_rate_at_purchase) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                )
                cursor.execute(insert_sql, (
                    current_user["id"], symbol, item['amount'], price_buy,
                    purchase_date, base_currency, source, commission,
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
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )
        cursor.execute(history_sql, (current_user["id"], 'binance', now, imported_count, 'success' if imported_count > 0 else 'partial', now))
        conn.commit()
        conn.close()
        logger.info(f"✅ Binance import completed: {imported_count} items imported for user {current_user['id']}")

        # Generate AI predictions for imported symbols (non-blocking)
        imported_symbols = [item['symbol'] for item in result['portfolio_items']]
        await generate_predictions_for_symbols(imported_symbols)

        return {
            'success': True,
            'message': f'Successfully imported {imported_count} portfolio items from Binance',
            'items_imported': imported_count,
            'total_found': len(result['portfolio_items']),
            'items_with_missing_data': items_with_missing_data
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
        imported_count = 0
        now = datetime.now().isoformat() + "Z"
        items_with_missing_data = []

        for item in result['portfolio_items']:
            try:
                check_duplicate_sql = _normalize_placeholders(
                    "SELECT id FROM portfolio_items WHERE user_id = %s AND symbol = %s AND ABS(amount - %s) < 0.001"
                )
                cursor.execute(check_duplicate_sql, (current_user["id"], item['symbol'], item['amount']))
                if cursor.fetchone():
                    logger.info(f"Skipping duplicate item: {item['symbol']}")
                    continue
                currency_service.ensure_rates_initialized()
                base_currency = item.get('base_currency', 'USD')
                price_buy = item['price_buy']
                commission = item.get('commission', 0.0)
                purchase_date = item.get('purchase_date')
                
                # Check for missing data
                missing_fields = []
                if not price_buy or price_buy == 0:
                    missing_fields.append('Buy Price')
                if not purchase_date or purchase_date == '' or purchase_date == 'Unknown':
                    missing_fields.append('Purchase Date')
                
                # Track items with missing data
                if missing_fields:
                    items_with_missing_data.append({
                        'symbol': item['symbol'],
                        'missing_fields': missing_fields,
                        'amount': item['amount']
                    })
                
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
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
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
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )
        cursor.execute(history_sql, (current_user["id"], 'Bitfinex', now, imported_count, 'success' if imported_count > 0 else 'partial', now))
        conn.commit()
        conn.close()
        logger.info(f"✅ Bitfinex import completed: {imported_count} items imported for user {current_user['id']}")

        # Generate AI predictions for imported symbols (non-blocking)
        imported_symbols = [item['symbol'] for item in result['portfolio_items']]
        await generate_predictions_for_symbols(imported_symbols)

        return {
            'success': True,
            'message': f'Successfully imported {imported_count} portfolio items from Bitfinex',
            'items_imported': imported_count,
            'total_found': len(result['portfolio_items']),
            'items_with_missing_data': items_with_missing_data
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
        history_sql = _normalize_placeholders(
            "SELECT source, import_date, items_imported, status, error_message, created_at "
            "FROM import_history WHERE user_id = %s ORDER BY created_at DESC"
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

