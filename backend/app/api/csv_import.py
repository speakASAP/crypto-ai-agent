import json
from datetime import datetime
from typing import Dict, Any
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form

from ..dependencies.auth import get_current_active_user, get_db_connection
from ..services.csv_import_service import CSVImportService
from ..services.currency_service import currency_service
from ..schemas.csv_import import CSVUploadResponse
from ..utils.logger import get_logger
from ..utils.db import normalize_placeholders as _normalize_placeholders


router = APIRouter(prefix="/api/import/csv", tags=["csv-import"])
logger = get_logger("backend.app.api.csv_import")
csv_import_service = CSVImportService()


@router.post("/upload", response_model=CSVUploadResponse)
async def upload_csv_file(file: UploadFile = File(...), current_user: dict = Depends(get_current_active_user)):
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV file")
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
        rows = csv_import_service.parse_csv_file(content)
        if not rows:
            return CSVUploadResponse(success=False, message="CSV file is empty or invalid", errors=["No data found in CSV file"])
        headers = list(rows[0].keys()) if rows else []
        detected_exchange = csv_import_service.detect_exchange_format(headers)
        if not detected_exchange:
            return CSVUploadResponse(
                success=False,
                message="Could not detect exchange format. Please use a supported exchange or manually map columns.",
                preview_data=rows[:5],
                total_rows=len(rows),
                errors=["No matching exchange template found"],
            )
        template = csv_import_service.get_template(detected_exchange)
        normalized_txns = []
        errors = []
        for i, row in enumerate(rows, start=2):
            txn = csv_import_service.normalize_transaction(row, template, detected_exchange)
            if txn:
                normalized_txns.append(txn)
            else:
                errors.append(f"Row {i}: Failed to parse transaction")
        if not normalized_txns:
            return CSVUploadResponse(
                success=False,
                message="No valid transactions found in CSV",
                detected_exchange=detected_exchange,
                total_rows=len(rows),
                errors=errors,
            )
        aggregated_items = csv_import_service.aggregate_transactions(normalized_txns)
        
        # Analyze what will happen to existing portfolio items
        conn = get_db_connection()
        cursor = conn.cursor()
        
        items_to_add = []
        items_to_update = []
        items_to_delete = []
        
        for item in aggregated_items:
            symbol = item['symbol']
            net_change = item.get('net_change', item.get('quantity', 0))
            
            # Check if portfolio item exists (case-insensitive)
            check_existing_sql = (
                "SELECT id, amount FROM portfolio_items WHERE user_id = %s AND UPPER(symbol) = UPPER(%s)"
            )
            cursor.execute(check_existing_sql, (current_user["id"], symbol))
            existing_item = cursor.fetchone()
            
            if existing_item:
                existing_amount = existing_item[1]
                new_amount = existing_amount + net_change
                
                if new_amount <= 0:
                    # Will be deleted
                    items_to_delete.append({
                        'symbol': symbol,
                        'current_amount': existing_amount,
                        'net_change': net_change,
                        'will_be_deleted': True
                    })
                else:
                    # Will be updated
                    items_to_update.append({
                        'symbol': symbol,
                        'current_amount': existing_amount,
                        'net_change': net_change,
                        'new_amount': new_amount,
                        'csv_quantity': item.get('quantity', 0),
                        'csv_price': item.get('price', 0)
                    })
            else:
                # Will be added (only if net_change > 0)
                if net_change > 0:
                    items_to_add.append({
                        'symbol': symbol,
                        'quantity': item.get('quantity', 0),
                        'price': item.get('price', 0),
                        'currency': item.get('currency', 'USD')
                    })
                # If net_change <= 0 and doesn't exist, it means selling non-existent position (warning already handled)
        
        conn.close()
        
        # Build summary message
        action_summary = []
        if items_to_add:
            action_summary.append(f"{len(items_to_add)} will be added")
        if items_to_update:
            action_summary.append(f"{len(items_to_update)} will be updated")
        if items_to_delete:
            action_summary.append(f"{len(items_to_delete)} will be removed")
        
        summary_text = f"Found {len(aggregated_items)} unique symbols from {len(normalized_txns)} transactions."
        if action_summary:
            summary_text += f" After import: {', '.join(action_summary)}."
        
        return CSVUploadResponse(
            success=True,
            message=summary_text,
            detected_exchange=detected_exchange,
            preview_data=normalized_txns[:10],
            total_rows=len(rows),
            aggregated_items=aggregated_items,
            errors=errors[:10] if errors else [],
            items_to_add=items_to_add,
            items_to_update=items_to_update,
            items_to_delete=items_to_delete,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading CSV file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process CSV file: {str(e)}")


@router.post("/execute")
async def execute_csv_import(file: UploadFile = File(...), exchange: str = Form(...), current_user: dict = Depends(get_current_active_user)):
    try:
        logger.info(f"🔵 CSV execute import started by user {current_user['id']}")
        logger.info(f"📊 Exchange parameter: {exchange}")
        content = await file.read()
        logger.info(f"📁 Read {len(content)} bytes from CSV file")
        rows = csv_import_service.parse_csv_file(content)
        logger.info(f"✅ Parsed {len(rows)} rows from CSV")
        if not rows:
            logger.error("❌ CSV file is empty or invalid")
            raise HTTPException(status_code=400, detail="CSV file sort is empty or invalid")
        template = csv_import_service.get_template(exchange)
        if not template:
            logger.error(f"❌ Unknown exchange: {exchange}")
            raise HTTPException(status_code=400, detail=f"Unknown exchange: {exchange}")
        logger.info(f"✅ Template found for {exchange}")
        normalized_txns = []
        for idx, row in enumerate(rows):
            txn = csv_import_service.normalize_transaction(row, template, exchange)
            if txn:
                normalized_txns.append(txn)
            elif idx < 5:
                logger.warning(f"⚠️ Failed to normalize transaction {idx}: {row}")
        logger.info(f"✅ Normalized {len(normalized_txns)} transactions")
        if not normalized_txns:
            logger.error("❌ No valid transactions found in CSV")
            raise HTTPException(status_code=400, detail="No valid transactions found in CSV")
        aggregated_items = csv_import_service.aggregate_transactions(normalized_txns)
        logger.info(f"✅ Aggregated to {len(aggregated_items)} positions")
        if not aggregated_items:
            logger.error("❌ No valid positions after aggregation")
            raise HTTPException(status_code=400, detail="No valid positions after aggregation")
        logger.info("💾 Saving to database...")
        conn = get_db_connection()
        cursor = conn.cursor()
        imported_count = 0
        updated_count = 0
        deleted_count = 0
        now = datetime.now().isoformat() + "Z"

        for item in aggregated_items:
            try:
                symbol = item['symbol']
                net_change = item.get('net_change', item.get('quantity', 0))
                is_sell_only = item.get('is_sell_only', False)
                logger.info(f"📦 Processing aggregated item: {symbol}, net_change={net_change}, is_sell_only={is_sell_only}, quantity={item.get('quantity', 0)}")

                # Check if portfolio item exists by symbol only (not quantity)
                # Use UPPER() for case-insensitive comparison since CSV symbols are normalized to uppercase
                # Also trim whitespace from symbol for matching
                symbol_normalized = symbol.strip().upper() if symbol else symbol
                check_existing_sql = (
                    "SELECT id, amount, price_buy, commission, base_currency, price_buy_usd, commission_usd, exchange_rate_at_purchase "
                    "FROM portfolio_items WHERE user_id = %s AND UPPER(TRIM(symbol)) = UPPER(TRIM(%s))"
                )
                cursor.execute(check_existing_sql, (current_user["id"], symbol_normalized))
                existing_item = cursor.fetchone()
                if existing_item:
                    logger.info(f"✅ Found existing portfolio item for {symbol}: id={existing_item[0]}, amount={existing_item[1]}")
                else:
                    logger.info(f"ℹ️ No existing portfolio item found for {symbol}")

                currency = item.get('currency', 'USD')
                currency_service.ensure_rates_initialized()

                if existing_item:
                    # Portfolio item exists - merge with existing data
                    existing_id = existing_item[0]
                    existing_amount = existing_item[1]
                    existing_price = existing_item[2]
                    existing_commission = existing_item[3] if existing_item[3] else 0.0
                    existing_currency = existing_item[4]
                    existing_price_usd = existing_item[5] if existing_item[5] else None
                    existing_commission_usd = existing_item[6] if existing_item[6] else 0.0
                    existing_exchange_rate = existing_item[7]

                    # Calculate new amount after applying CSV net change
                    # Use Decimal for precision (at least 8 decimal places)
                    existing_amount_decimal = Decimal(str(existing_amount))
                    net_change_decimal = Decimal(str(net_change))
                    new_amount_decimal = existing_amount_decimal + net_change_decimal
                    new_amount = float(new_amount_decimal)
                    epsilon = Decimal('1e-10')  # Very small threshold for floating point comparison only

                    logger.info(f"🔍 Processing {symbol}: existing={existing_amount}, net_change={net_change}, new_amount={new_amount}")

                    # Only delete if amount is 0 or effectively 0 (due to floating point precision)
                    # Keep small amounts - only delete when truly zero
                    if new_amount_decimal <= epsilon:
                        # Fully sold or over-sold: DELETE portfolio item
                        delete_sql = _normalize_placeholders(
                            "DELETE FROM portfolio_items WHERE id = %s AND user_id = %s"
                        )
                        logger.info(f"🗑️ Executing DELETE for {symbol}: id={existing_id}, user_id={current_user['id']}")
                        cursor.execute(delete_sql, (existing_id, current_user["id"]))
                        deleted_count += 1
                        logger.info(f"🗑️ Deleted {symbol} (sold completely, was {existing_amount}, sold {abs(net_change)}, new_amount={new_amount})")
                    else:
                        logger.info(f"⚠️ {symbol} NOT deleted: new_amount={new_amount} > epsilon={epsilon} (partial sell or net increase)")
                        # Partial sell or additional buy: UPDATE portfolio item
                        # Calculate weighted average price
                        if is_sell_only:
                            # Sell-only: keep existing price (we're reducing quantity, not changing buy price)
                            merged_price = existing_price
                            merged_price_usd = existing_price_usd if existing_price_usd else existing_price
                            # Commission stays the same (we already paid it)
                            merged_commission = existing_commission
                            merged_commission_usd = existing_commission_usd
                            merged_exchange_rate = existing_exchange_rate
                        else:
                            # Has buys in CSV: calculate weighted average
                            # CSV price is already weighted average of buy transactions
                            csv_price = item['price']
                            csv_buy_qty = item.get('total_buy_qty', 0)  # Amount actually bought in CSV
                            
                            # For weighted average, we consider:
                            # - Existing holdings: existing_amount at existing_price
                            # - New buys from CSV: csv_buy_qty at csv_price
                            # If net_change is negative (more sold than bought), we keep existing price
                            
                            if net_change > 0:
                                # Net increase: calculate weighted average using Decimal for precision
                                # Convert existing price to same currency as CSV item if needed
                                existing_price_decimal = Decimal(str(existing_price))
                                csv_price_decimal = Decimal(str(csv_price))
                                csv_buy_qty_decimal = Decimal(str(csv_buy_qty))
                                existing_amount_decimal_calc = Decimal(str(existing_amount))
                                
                                existing_price_in_csv_currency = existing_price
                                if existing_currency != currency:
                                    # Convert existing price to CSV currency
                                    if currency != 'USD' and existing_currency != 'USD':
                                        # Both non-USD: convert existing to USD first, then to CSV currency
                                        existing_exchange_rate_used = existing_exchange_rate if existing_exchange_rate else 1.0
                                        existing_price_usd_calc = float(existing_price_decimal / Decimal(str(existing_exchange_rate_used)))
                                        csv_exchange_rate = currency_service.rates.get(currency, 1.0)
                                        existing_price_in_csv_currency = float(existing_price_usd_calc * Decimal(str(csv_exchange_rate)))
                                    elif existing_currency == 'USD' and currency != 'USD':
                                        csv_exchange_rate = currency_service.rates.get(currency, 1.0)
                                        existing_price_in_csv_currency = float(existing_price_decimal * Decimal(str(csv_exchange_rate)))

                                # Weighted average: (existing * existing_price + new_buys * csv_price) / (existing + new_buys)
                                # Use Decimal for all calculations
                                existing_price_csv_decimal = Decimal(str(existing_price_in_csv_currency))
                                existing_value_decimal = existing_amount_decimal_calc * existing_price_csv_decimal
                                csv_buy_value_decimal = csv_buy_qty_decimal * csv_price_decimal
                                total_value_decimal = existing_value_decimal + csv_buy_value_decimal
                                total_quantity_for_price_decimal = existing_amount_decimal_calc + csv_buy_qty_decimal
                                merged_price = float(total_value_decimal / total_quantity_for_price_decimal) if total_quantity_for_price_decimal > 0 else existing_price

                                # Calculate USD prices
                                if currency != 'USD':
                                    csv_exchange_rate = currency_service.rates.get(currency, 1.0)
                                    csv_exchange_rate_decimal = Decimal(str(csv_exchange_rate))
                                    csv_price_usd = float(csv_price_decimal / csv_exchange_rate_decimal)
                                else:
                                    csv_exchange_rate = None
                                    csv_price_usd = float(csv_price_decimal)

                                # Merge commission (only from buys, not sells)
                                existing_commission_decimal = Decimal(str(existing_commission))
                                item_fees_decimal = Decimal(str(item.get('fees', 0)))
                                merged_commission = float(existing_commission_decimal + item_fees_decimal)
                                
                                if existing_price_usd:
                                    existing_price_usd_decimal = Decimal(str(existing_price_usd))
                                    existing_value_usd_decimal = existing_amount_decimal_calc * existing_price_usd_decimal
                                    existing_value_usd = float(existing_value_usd_decimal)
                                else:
                                    csv_price_usd_decimal = Decimal(str(csv_price_usd))
                                    existing_value_usd_decimal = existing_amount_decimal_calc * csv_price_usd_decimal
                                    existing_value_usd = float(existing_value_usd_decimal)  # Fallback

                                csv_price_usd_decimal = Decimal(str(csv_price_usd))
                                csv_buy_value_usd_decimal = csv_buy_qty_decimal * csv_price_usd_decimal
                                total_value_usd_decimal = Decimal(str(existing_value_usd)) + csv_buy_value_usd_decimal
                                merged_price_usd = float(total_value_usd_decimal / total_quantity_for_price_decimal) if total_quantity_for_price_decimal > 0 else (existing_price_usd or csv_price_usd)
                                
                                if currency != 'USD':
                                    csv_exchange_rate_decimal = Decimal(str(csv_exchange_rate))
                                    existing_commission_usd_decimal = Decimal(str(existing_commission_usd))
                                    merged_commission_usd = float(existing_commission_usd_decimal + (item_fees_decimal / csv_exchange_rate_decimal))
                                    merged_exchange_rate = csv_exchange_rate
                                else:
                                    existing_commission_usd_decimal = Decimal(str(existing_commission_usd))
                                    merged_commission_usd = float(existing_commission_usd_decimal + item_fees_decimal)
                                    merged_exchange_rate = None
                            else:
                                # Net decrease (partial sell): keep existing price
                                merged_price = existing_price
                                merged_price_usd = existing_price_usd if existing_price_usd else existing_price
                                merged_commission = existing_commission  # Don't add fees from sells
                                merged_commission_usd = existing_commission_usd
                                if currency != 'USD':
                                    merged_exchange_rate = currency_service.rates.get(currency, 1.0)
                                else:
                                    merged_exchange_rate = existing_exchange_rate

                        # Calculate total investment for display (using Decimal for precision)
                        new_amount_decimal_display = Decimal(str(new_amount))
                        merged_price_decimal = Decimal(str(merged_price))
                        merged_price_usd_decimal = Decimal(str(merged_price_usd))
                        merged_commission_decimal = Decimal(str(merged_commission))
                        merged_commission_usd_decimal = Decimal(str(merged_commission_usd))
                        
                        if currency != 'USD':
                            exchange_rate_for_display = currency_service.rates.get(currency, 1.0)
                            exchange_rate_decimal = Decimal(str(exchange_rate_for_display))
                            total_investment_usd_decimal = (new_amount_decimal_display * merged_price_usd_decimal) + merged_commission_usd_decimal
                            total_investment = float(total_investment_usd_decimal * exchange_rate_decimal)
                        else:
                            total_investment = float((new_amount_decimal_display * merged_price_decimal) + merged_commission_decimal)

                        currency_symbols = {'USD': '$', 'EUR': '€', 'CZK': 'Kč', 'GBP': '£', 'JPY': '¥'}
                        currency_symbol = currency_symbols.get(currency, currency + ' ')
                        total_investment_text = f"{currency_symbol}{total_investment:.2f}"

                        # Update portfolio item
                        update_sql = _normalize_placeholders(
                            "UPDATE portfolio_items SET "
                            "amount = %s, price_buy = %s, commission = %s, "
                            "price_buy_usd = %s, commission_usd = %s, exchange_rate_at_purchase = %s, "
                            "total_investment_text = %s, updated_at = %s, source = %s "
                            "WHERE id = %s AND user_id = %s"
                        )
                        cursor.execute(update_sql, (
                            new_amount, merged_price, merged_commission,
                            merged_price_usd, merged_commission_usd, merged_exchange_rate,
                            total_investment_text, now, exchange.capitalize(),
                            existing_id, current_user["id"]
                        ))
                        updated_count += 1
                        logger.info(f"🔄 Updated {symbol}: {existing_amount} -> {new_amount} (change: {net_change:+.8f})")
                else:
                    # Portfolio item doesn't exist
                    logger.info(f"📋 {symbol} not found in portfolio (net_change={net_change})")
                    if net_change > 0:
                        # Insert new item (net change is positive = buy)
                        # Use Decimal for all calculations to preserve precision
                        item_price_decimal = Decimal(str(item['price']))
                        item_quantity_decimal = Decimal(str(item['quantity']))
                        item_fees_decimal = Decimal(str(item.get('fees', 0)))
                        item_value_decimal = Decimal(str(item.get('value', 0)))
                        
                        if currency != 'USD':
                            exchange_rate = currency_service.rates.get(currency, 1.0)
                            exchange_rate_decimal = Decimal(str(exchange_rate))
                            price_usd = float(item_price_decimal / exchange_rate_decimal)
                            fees_usd = float(item_fees_decimal / exchange_rate_decimal) if item['fees'] > 0 else 0.0
                            value_usd = float(item_value_decimal / exchange_rate_decimal) if item.get('value', 0) > 0 else 0.0
                        else:
                            exchange_rate = None
                            price_usd = float(item_price_decimal)
                            fees_usd = float(item_fees_decimal)
                            value_usd = float(item_value_decimal)

                        if item.get('value', 0) > 0:
                            total_investment = float(item_value_decimal + item_fees_decimal)
                        else:
                            total_investment = float(item_quantity_decimal * item_price_decimal + item_fees_decimal)

                        currency_symbols = {'USD': '$', 'EUR': '€', 'CZK': 'Kč', 'GBP': '£', 'JPY': '¥'}
                        currency_symbol = currency_symbols.get(currency, currency + ' ')
                        total_investment_text = f"{currency_symbol}{total_investment:.2f}"

                        insert_sql = _normalize_placeholders(
                            "INSERT INTO portfolio_items "
                            "(user_id, symbol, amount, price_buy, purchase_date, base_currency, source, commission, "
                            "total_investment_text, created_at, updated_at, price_buy_usd, commission_usd, exchange_rate_at_purchase) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                        )
                        cursor.execute(insert_sql, (
                            current_user["id"], symbol, item['quantity'], item['price'],
                            item['date'], currency, exchange.capitalize(), item['fees'],
                            total_investment_text, now, now, price_usd, fees_usd, exchange_rate,
                        ))
                        imported_count += 1
                        logger.info(f"➕ Inserted new {symbol}: {item['quantity']}")
                    else:
                        # Selling non-existent position - log warning but don't create negative amount
                        logger.warning(f"⚠️ Attempted to sell {symbol} ({abs(net_change)}) that doesn't exist in portfolio - skipping")

            except Exception as e:
                logger.error(f"Failed to process item {item.get('symbol', 'unknown')}: {e}", exc_info=True)
                continue

        column_mapping_data = {
            'column_mapping': template.get('column_mapping', {}),
            'headers': list(rows[0].keys()) if rows else [],
        }

        # PostgreSQL: use ON CONFLICT DO UPDATE
        mapping_sql = (
            "INSERT INTO csv_import_mappings "
            "(user_id, exchange, column_mapping, created_at, updated_at, last_used) "
            "VALUES (%s, %s, %s, NOW(), NOW(), NOW()) "
            "ON CONFLICT (user_id, exchange) DO UPDATE SET "
            "column_mapping = EXCLUDED.column_mapping, updated_at = NOW(), last_used = NOW()"
        )
        cursor.execute(mapping_sql, (current_user["id"], exchange.lower(), json.dumps(column_mapping_data)))

        total_processed = imported_count + updated_count + deleted_count
        history_sql = _normalize_placeholders(
            "INSERT INTO import_history "
            "(user_id, source, import_date, items_imported, status, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )
        cursor.execute(history_sql, (current_user["id"], exchange.capitalize(), now, total_processed, 'success' if total_processed > 0 else 'partial', now))

        conn.commit()
        conn.close()

        logger.info(f"✅ CSV import completed for user {current_user['id']}: {imported_count} inserted, {updated_count} updated, {deleted_count} deleted")

        # Immediately fetch prices for newly imported symbols
        imported_symbols = list(set(item['symbol'] for item in aggregated_items))
        if imported_symbols:
            try:
                from ..main import fetch_prices_for_symbols
                logger.info(f"🔄 Fetching prices for {len(imported_symbols)} imported symbols: {imported_symbols}")
                await fetch_prices_for_symbols(imported_symbols)
                logger.info(f"✅ Price update completed for imported symbols")
            except Exception as e:
                logger.error(f"⚠️ Failed to fetch prices for imported symbols: {e}", exc_info=True)
                # Don't fail the import if price fetch fails

        total_processed = imported_count + updated_count + deleted_count
        return {
            'success': True,
            'message': f'Successfully processed CSV: {imported_count} inserted, {updated_count} updated, {deleted_count} deleted',
            'items_imported': imported_count,
            'items_updated': updated_count,
            'items_deleted': deleted_count,
            'total_processed': total_processed,
            'total_found': len(aggregated_items),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing CSV import: {e}")
        raise HTTPException(status_code=500, detail=f"Import execution failed: {str(e)}")


@router.get("/templates")
async def get_csv_templates():
    try:
        templates = []
        for exchange, template in csv_import_service.templates.items():
            templates.append({
                'exchange': exchange,
                'name': template.get('name', exchange),
                'required_fields': template.get('required_fields', []),
                'optional_fields': template.get('optional_fields', []),
            })
        return {'templates': templates}
    except Exception as e:
        logger.error(f"Error getting CSV templates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get templates: {str(e)}")


@router.get("/mapping/{exchange}")
async def get_csv_mapping(exchange: str, current_user: dict = Depends(get_current_active_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = _normalize_placeholders(
            "SELECT column_mapping FROM csv_import_mappings WHERE user_id = %s AND exchange = %s"
        )
        cursor.execute(sql, (current_user["id"], exchange.lower()))
        result = cursor.fetchone()
        conn.close()
        if result:
            return {'mapping': json.loads(result[0])}
        else:
            raise HTTPException(status_code=404, detail="Mapping not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting CSV mapping: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get mapping: {str(e)}")


@router.post("/mapping/{exchange}")
async def save_csv_mapping(exchange: str, mapping_data: Dict[str, Any], current_user: dict = Depends(get_current_active_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # PostgreSQL: use ON CONFLICT DO UPDATE
        sql = (
            "INSERT INTO csv_import_mappings "
            "(user_id, exchange, column_mapping, created_at, updated_at, last_used) "
            "VALUES (%s, %s, %s, NOW(), NOW(), NOW()) "
            "ON CONFLICT (user_id, exchange) DO UPDATE SET "
            "column_mapping = EXCLUDED.column_mapping, updated_at = NOW(), last_used = NOW()"
        )
        cursor.execute(sql, (current_user["id"], exchange.lower(), json.dumps(mapping_data)))
        conn.commit()
        conn.close()
        return {'message': 'Mapping saved successfully'}
    except Exception as e:
        logger.error(f"Error saving CSV mapping: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save mapping: {str(e)}")

