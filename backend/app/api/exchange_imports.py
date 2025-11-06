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
        items_with_issues = []  # Track all items with issues (not just missing data)
        
        # Get current prices for fallback when price is missing
        from ..services.multi_exchange_price_service import multi_exchange_price_service
        all_symbols = [item['symbol'].upper() for item in result['portfolio_items']]
        current_prices = await multi_exchange_price_service.get_current_prices(all_symbols)

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
                price_buy = item.get('price_buy', 0)
                commission = item.get('commission', 0.0)
                purchase_date = item.get('purchase_date')
                
                # Track all issues for this item
                issues = []
                warnings = []
                
                # Check if service layer used fallback price
                needs_price_fallback = item.get('_needs_price_fallback', False)
                if needs_price_fallback:
                    if price_buy and price_buy > 0 and price_buy != 9999999.0:
                        warnings.append(f"Missing buy price - used current market price (${price_buy:.2f}) as fallback. Please verify and update manually.")
                    elif price_buy == 9999999.0:
                        issues.append("CRITICAL: Missing buy price - could not fetch current market price. Using fallback 9999999. MUST be updated manually.")
                
                # Check for missing or invalid price
                price_was_missing = False
                if not price_buy or price_buy <= 0:
                    # Try to use current market price as fallback
                    if symbol in current_prices and current_prices[symbol] > 0:
                        price_buy = current_prices[symbol]
                        price_was_missing = True
                        warnings.append(f"Missing buy price - used current market price (${price_buy:.2f}) as fallback. Please verify and update manually.")
                        logger.info(f"⚠️ {symbol}: Missing buy price - used current market price ${price_buy:.2f} as fallback")
                    else:
                        # Last resort: use huge amount (9999999) to alert user
                        price_buy = 9999999.0
                        price_was_missing = True
                        issues.append("CRITICAL: Missing buy price - could not fetch current market price. Using fallback 9999999. MUST be updated manually.")
                        logger.warning(f"❌ {symbol}: Missing buy price - could not fetch market price, using fallback 9999999")
                
                # Check for missing purchase date
                if not purchase_date or purchase_date == '' or purchase_date == 'Unknown':
                    purchase_date = datetime.now().isoformat()
                    warnings.append("Missing purchase date - used current date as fallback. Please update with the actual purchase date.")
                
                # Calculate price_buy_usd
                try:
                    if base_currency != 'USD':
                        exchange_rate = currency_service.rates.get(base_currency, 1.0) if base_currency in currency_service.rates else 1.0
                        if exchange_rate <= 0:
                            exchange_rate = 1.0
                            warnings.append(f"Invalid exchange rate for {base_currency} - used 1.0. Price conversion may be inaccurate.")
                        price_buy_usd = price_buy / exchange_rate if exchange_rate > 0 else price_buy
                        commission_usd = commission / exchange_rate if exchange_rate > 0 else commission
                    else:
                        price_buy_usd = price_buy
                        commission_usd = commission
                        exchange_rate = 1.0
                    
                    # Validate price_buy_usd
                    if not price_buy_usd or price_buy_usd <= 0:
                        # Use current market price as fallback
                        if symbol in current_prices and current_prices[symbol] > 0:
                            price_buy_usd = current_prices[symbol]
                            warnings.append(f"Invalid calculated price_buy_usd - used current market price (${price_buy_usd:.2f}) as fallback.")
                        else:
                            price_buy_usd = 9999999.0
                            issues.append("CRITICAL: Invalid calculated price_buy_usd - using fallback 9999999. MUST be updated manually.")
                            logger.warning(f"⚠️ {symbol}: Invalid calculated price_buy_usd (currency={base_currency}, rate={exchange_rate}, price_buy={price_buy}), using fallback 9999999")
                except Exception as e:
                    logger.warning(f"⚠️ Error calculating price_buy_usd for {symbol}: {e} (currency={base_currency}, price_buy={price_buy})", exc_info=True)
                    # Use current market price as fallback
                    if symbol in current_prices and current_prices[symbol] > 0:
                        price_buy_usd = current_prices[symbol]
                        warnings.append(f"Error calculating price - used current market price (${price_buy_usd:.2f}) as fallback.")
                    else:
                        price_buy_usd = 9999999.0
                        issues.append(f"CRITICAL: Error calculating price: {str(e)}. Using fallback 9999999. MUST be updated manually.")
                        logger.error(f"❌ {symbol}: Failed to calculate price_buy_usd, using fallback 9999999")
                
                # Track item if it has any issues or warnings
                if issues or warnings:
                    items_with_issues.append({
                        'symbol': symbol,
                        'amount': item['amount'],
                        'issues': issues,
                        'warnings': warnings,
                        'price_buy': price_buy,
                        'price_buy_usd': price_buy_usd,
                        'purchase_date': purchase_date
                    })
                
                # CRITICAL: Final validation before insert - ensure price_buy_usd > 0 (never skip - import everything)
                if not price_buy_usd or price_buy_usd <= 0:
                    if symbol in current_prices and current_prices[symbol] > 0:
                        price_buy_usd = current_prices[symbol]
                        price_buy = price_buy_usd if base_currency == 'USD' else price_buy_usd * exchange_rate
                        warnings.append(f"Final validation: Used current market price (${price_buy_usd:.2f}) as fallback.")
                    else:
                        price_buy_usd = 9999999.0
                        price_buy = 9999999.0 if base_currency == 'USD' else 9999999.0 * exchange_rate
                        issues.append("CRITICAL: Could not determine price - using fallback 9999999. MUST be updated manually.")
                        logger.error(f"❌ {symbol}: Final validation failed - using fallback 9999999 (currency={base_currency}, rate={exchange_rate})")
                
                # Explicit validation: price_buy_usd MUST be > 0
                if price_buy_usd <= 0:
                    logger.error(f"❌ {symbol}: price_buy_usd is {price_buy_usd}, forcing to 9999999")
                    price_buy_usd = 9999999.0
                    price_buy = 9999999.0 if base_currency == 'USD' else 9999999.0 * exchange_rate
                    issues.append("CRITICAL: price_buy_usd validation failed - using fallback 9999999. MUST be updated manually.")
                
                if not purchase_date:
                    purchase_date = datetime.now().isoformat()
                    warnings.append("Missing purchase date - used current date. Please update with actual purchase date.")
                
                if commission_usd is None:
                    commission_usd = 0.0
                
                # Generate total_investment_text if missing
                total_investment_text = item.get('total_investment_text')
                if not total_investment_text:
                    total_investment = (item['amount'] * price_buy) + commission
                    if base_currency == 'USD':
                        total_investment_text = f"${total_investment:.2f}"
                    elif base_currency == 'EUR':
                        total_investment_text = f"€{total_investment:.2f}"
                    elif base_currency == 'CZK':
                        total_investment_text = f"{total_investment:.2f} Kč"
                    else:
                        total_investment_text = f"{total_investment:.2f} {base_currency}"
                
                # New item - insert it (same symbol from different sources are allowed)
                # CRITICAL: Always import - never skip
                insert_sql = _normalize_placeholders(
                    "INSERT INTO portfolio_items "
                    "(user_id, symbol, amount, price_buy, purchase_date, base_currency, source, commission, "
                    "total_investment_text, created_at, updated_at, current_price, current_value, pnl, pnl_percent, "
                    "price_buy_usd, commission_usd, exchange_rate_at_purchase) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                )
                try:
                    cursor.execute(insert_sql, (
                        current_user["id"], symbol, item['amount'], round(price_buy, 8),
                        purchase_date, base_currency, source, commission,
                        total_investment_text, now, now,
                        round(price_buy, 8), round(item['amount'] * price_buy, 8), 0.0, 0.0,
                        round(price_buy_usd, 8), round(commission_usd, 8), exchange_rate
                    ))
                    imported_count += 1
                    logger.info(f"✅ Imported {symbol}: amount={item['amount']}, price_buy_usd={price_buy_usd:.8f}, currency={base_currency}, rate={exchange_rate}")
                except Exception as db_error:
                    # Catch database constraint violations
                    error_msg = str(db_error)
                    logger.error(f"❌ Database error inserting {symbol}: {error_msg} (price_buy_usd={price_buy_usd}, currency={base_currency}, rate={exchange_rate})", exc_info=True)
                    # Still track as issue and try to continue with other items
                    issues.append(f"Database error: {error_msg}. Item was NOT imported. Please add manually.")
                    items_with_issues.append({
                        'symbol': symbol,
                        'amount': item['amount'],
                        'issues': issues,
                        'warnings': warnings,
                        'price_buy': price_buy,
                        'price_buy_usd': price_buy_usd,
                        'purchase_date': purchase_date
                    })
                    # Re-raise to ensure transaction is rolled back if needed
                    raise
            except Exception as e:
                logger.error(f"❌ Failed to import item {item.get('symbol', 'UNKNOWN')}: {e}", exc_info=True)
                # Still track the item with error
                symbol = item.get('symbol', 'UNKNOWN').upper()
                items_with_issues.append({
                    'symbol': symbol,
                    'amount': item.get('amount', 0),
                    'issues': [f"Import failed: {str(e)}. Item was NOT imported. Please add manually."],
                    'warnings': [],
                    'price_buy': 0,
                    'price_buy_usd': 0,
                    'purchase_date': None
                })
                # DO NOT continue - we want to process all items, but track errors

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
            'items_with_issues': items_with_issues  # Changed from items_with_missing_data to items_with_issues
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
        items_with_issues = []  # Track all items with issues
        
        # Get current prices for fallback when price is missing
        from ..services.multi_exchange_price_service import multi_exchange_price_service
        all_symbols = [item['symbol'].upper() for item in result['portfolio_items']]
        current_prices = await multi_exchange_price_service.get_current_prices(all_symbols)

        for item in result['portfolio_items']:
            try:
                symbol = item['symbol'].upper()
                source = item.get('source', 'Bitfinex')
                
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
                price_buy = item.get('price_buy', 0)
                commission = item.get('commission', 0.0)
                purchase_date = item.get('purchase_date')
                
                # Track all issues for this item
                issues = []
                warnings = []
                
                # Check if service layer used fallback price
                needs_price_fallback = item.get('_needs_price_fallback', False)
                if needs_price_fallback:
                    if price_buy and price_buy > 0 and price_buy != 9999999.0:
                        warnings.append(f"Missing buy price - used current market price (${price_buy:.2f}) as fallback. Please verify and update manually.")
                    elif price_buy == 9999999.0:
                        issues.append("CRITICAL: Missing buy price - could not fetch current market price. Using fallback 9999999. MUST be updated manually.")
                
                # Check for missing or invalid price
                symbol_upper = item['symbol'].upper()
                if not price_buy or price_buy <= 0:
                    # Try to use current market price as fallback
                    if symbol_upper in current_prices and current_prices[symbol_upper] > 0:
                        price_buy = current_prices[symbol_upper]
                        warnings.append(f"Missing buy price - used current market price (${price_buy:.2f}) as fallback. Please verify and update manually.")
                        logger.info(f"⚠️ {symbol}: Missing buy price - used current market price ${price_buy:.2f} as fallback")
                    else:
                        # Last resort: use huge amount (9999999) to alert user
                        price_buy = 9999999.0
                        issues.append("CRITICAL: Missing buy price - could not fetch current market price. Using fallback 9999999. MUST be updated manually.")
                        logger.warning(f"❌ {symbol}: Missing buy price - could not fetch market price, using fallback 9999999")
                
                # Check for missing purchase date
                if not purchase_date or purchase_date == '' or purchase_date == 'Unknown':
                    purchase_date = datetime.now().isoformat()
                    warnings.append("Missing purchase date - used current date as fallback. Please update with the actual purchase date.")
                
                # Calculate price_buy_usd
                try:
                    if base_currency != 'USD':
                        exchange_rate = currency_service.rates.get(base_currency, 1.0) if base_currency in currency_service.rates else 1.0
                        if exchange_rate <= 0:
                            exchange_rate = 1.0
                            warnings.append(f"Invalid exchange rate for {base_currency} - used 1.0. Price conversion may be inaccurate.")
                        price_buy_usd = price_buy / exchange_rate if exchange_rate > 0 else price_buy
                        commission_usd = commission / exchange_rate if exchange_rate > 0 else commission
                    else:
                        price_buy_usd = price_buy
                        commission_usd = commission
                        exchange_rate = 1.0
                    
                    # Validate price_buy_usd
                    if not price_buy_usd or price_buy_usd <= 0:
                        # Use current market price as fallback
                        if symbol_upper in current_prices and current_prices[symbol_upper] > 0:
                            price_buy_usd = current_prices[symbol_upper]
                            warnings.append(f"Invalid calculated price_buy_usd - used current market price (${price_buy_usd:.2f}) as fallback.")
                        else:
                            price_buy_usd = 9999999.0
                            issues.append("CRITICAL: Invalid calculated price_buy_usd - using fallback 9999999. MUST be updated manually.")
                            logger.warning(f"⚠️ {symbol}: Invalid calculated price_buy_usd (currency={base_currency}, rate={exchange_rate}, price_buy={price_buy}), using fallback 9999999")
                except Exception as e:
                    logger.warning(f"⚠️ Error calculating price_buy_usd for {symbol}: {e} (currency={base_currency}, price_buy={price_buy})", exc_info=True)
                    # Use current market price as fallback
                    if symbol_upper in current_prices and current_prices[symbol_upper] > 0:
                        price_buy_usd = current_prices[symbol_upper]
                        warnings.append(f"Error calculating price - used current market price (${price_buy_usd:.2f}) as fallback.")
                    else:
                        price_buy_usd = 9999999.0
                        issues.append(f"CRITICAL: Error calculating price: {str(e)}. Using fallback 9999999. MUST be updated manually.")
                        logger.error(f"❌ {symbol}: Failed to calculate price_buy_usd, using fallback 9999999")
                
                # Track item if it has any issues or warnings
                if issues or warnings:
                    items_with_issues.append({
                        'symbol': symbol,
                        'amount': item['amount'],
                        'issues': issues,
                        'warnings': warnings,
                        'price_buy': price_buy,
                        'price_buy_usd': price_buy_usd,
                        'purchase_date': purchase_date
                    })
                
                # CRITICAL: Final validation before insert - ensure price_buy_usd > 0 (never skip - import everything)
                if not price_buy_usd or price_buy_usd <= 0:
                    if symbol_upper in current_prices and current_prices[symbol_upper] > 0:
                        price_buy_usd = current_prices[symbol_upper]
                        price_buy = price_buy_usd if base_currency == 'USD' else price_buy_usd * exchange_rate
                        warnings.append(f"Final validation: Used current market price (${price_buy_usd:.2f}) as fallback.")
                    else:
                        price_buy_usd = 9999999.0
                        price_buy = 9999999.0 if base_currency == 'USD' else 9999999.0 * exchange_rate
                        issues.append("CRITICAL: Could not determine price - using fallback 9999999. MUST be updated manually.")
                        logger.error(f"❌ {symbol}: Final validation failed - using fallback 9999999 (currency={base_currency}, rate={exchange_rate})")
                
                # Explicit validation: price_buy_usd MUST be > 0
                if price_buy_usd <= 0:
                    logger.error(f"❌ {symbol}: price_buy_usd is {price_buy_usd}, forcing to 9999999")
                    price_buy_usd = 9999999.0
                    price_buy = 9999999.0 if base_currency == 'USD' else 9999999.0 * exchange_rate
                    issues.append("CRITICAL: price_buy_usd validation failed - using fallback 9999999. MUST be updated manually.")
                
                if not purchase_date:
                    purchase_date = datetime.now().isoformat()
                    warnings.append("Missing purchase date - used current date. Please update with actual purchase date.")
                
                if commission_usd is None:
                    commission_usd = 0.0
                
                # Generate total_investment_text if missing
                total_investment_text = item.get('total_investment_text')
                if not total_investment_text:
                    total_investment = (item['amount'] * price_buy) + commission
                    if base_currency == 'USD':
                        total_investment_text = f"${total_investment:.2f}"
                    elif base_currency == 'EUR':
                        total_investment_text = f"€{total_investment:.2f}"
                    elif base_currency == 'CZK':
                        total_investment_text = f"{total_investment:.2f} Kč"
                    else:
                        total_investment_text = f"{total_investment:.2f} {base_currency}"
                
                # CRITICAL: Always import - never skip
                insert_sql = _normalize_placeholders(
                    "INSERT INTO portfolio_items "
                    "(user_id, symbol, amount, price_buy, purchase_date, base_currency, source, commission, "
                    "total_investment_text, created_at, updated_at, current_price, current_value, pnl, pnl_percent, "
                    "price_buy_usd, commission_usd, exchange_rate_at_purchase) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                )
                try:
                    cursor.execute(insert_sql, (
                        current_user["id"], symbol, item['amount'], round(price_buy, 8),
                        purchase_date, base_currency, source, commission,
                        total_investment_text, now, now,
                        round(price_buy, 8), round(item['amount'] * price_buy, 8), 0.0, 0.0,
                        round(price_buy_usd, 8), round(commission_usd, 8), exchange_rate
                    ))
                    imported_count += 1
                    logger.info(f"✅ Imported {symbol}: amount={item['amount']}, price_buy_usd={price_buy_usd:.8f}, currency={base_currency}, rate={exchange_rate}")
                except Exception as db_error:
                    # Catch database constraint violations
                    error_msg = str(db_error)
                    logger.error(f"❌ Database error inserting {symbol}: {error_msg} (price_buy_usd={price_buy_usd}, currency={base_currency}, rate={exchange_rate})", exc_info=True)
                    # Still track as issue and try to continue with other items
                    issues.append(f"Database error: {error_msg}. Item was NOT imported. Please add manually.")
                    items_with_issues.append({
                        'symbol': symbol,
                        'amount': item['amount'],
                        'issues': issues,
                        'warnings': warnings,
                        'price_buy': price_buy,
                        'price_buy_usd': price_buy_usd,
                        'purchase_date': purchase_date
                    })
                    # Re-raise to ensure transaction is rolled back if needed
                    raise
            except Exception as e:
                logger.error(f"❌ Failed to import item {item.get('symbol', 'UNKNOWN')}: {e}", exc_info=True)
                # Still track the item with error
                symbol = item.get('symbol', 'UNKNOWN').upper()
                items_with_issues.append({
                    'symbol': symbol,
                    'amount': item.get('amount', 0),
                    'issues': [f"Import failed: {str(e)}. Item was NOT imported. Please add manually."],
                    'warnings': [],
                    'price_buy': 0,
                    'price_buy_usd': 0,
                    'purchase_date': None
                })
                # DO NOT continue - we want to process all items, but track errors

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
            'items_with_issues': items_with_issues  # Changed from items_with_missing_data to items_with_issues
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

