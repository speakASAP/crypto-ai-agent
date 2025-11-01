import json
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form

from ..dependencies.auth import get_current_active_user, get_db_connection
from ..services.csv_import_service import CSVImportService
from ..services.currency_service import currency_service
from ..schemas.csv_import import CSVUploadResponse
from ..utils.logger import get_logger
from ..utils.db import normalize_placeholders as _normalize_placeholders, is_postgres_connection


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
        return CSVUploadResponse(
            success=True,
            message=f"Successfully parsed CSV file. Found {len(aggregated_items)} unique symbols from {len(normalized_txns)} transactions.",
            detected_exchange=detected_exchange,
            preview_data=normalized_txns[:10],
            total_rows=len(rows),
            aggregated_items=aggregated_items,
            errors=errors[:10] if errors else [],
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
        is_pg = is_postgres_connection(conn)
        imported_count = 0
        updated_count = 0
        deleted_count = 0
        now = datetime.now().isoformat() + "Z"

        for item in aggregated_items:
            try:
                symbol = item['symbol']
                net_change = item.get('net_change', item.get('quantity', 0))
                is_sell_only = item.get('is_sell_only', False)

                # Check if portfolio item exists by symbol only (not quantity)
                check_existing_sql = _normalize_placeholders(
                    "SELECT id, amount, price_buy, commission, base_currency, price_buy_usd, commission_usd, exchange_rate_at_purchase FROM portfolio_items WHERE user_id = ? AND symbol = ?",
                    is_pg
                )
                cursor.execute(check_existing_sql, (current_user["id"], symbol))
                existing_item = cursor.fetchone()

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
                    new_amount = existing_amount + net_change

                    if new_amount <= 0:
                        # Fully sold or over-sold: DELETE portfolio item
                        delete_sql = _normalize_placeholders(
                            "DELETE FROM portfolio_items WHERE id = ? AND user_id = ?",
                            is_pg
                        )
                        cursor.execute(delete_sql, (existing_id, current_user["id"]))
                        deleted_count += 1
                        logger.info(f"🗑️ Deleted {symbol} (sold completely, was {existing_amount}, sold {abs(net_change)})")
                    else:
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
                                # Net increase: calculate weighted average
                                # Convert existing price to same currency as CSV item if needed
                                existing_price_in_csv_currency = existing_price
                                if existing_currency != currency:
                                    # Convert existing price to CSV currency
                                    if currency != 'USD' and existing_currency != 'USD':
                                        # Both non-USD: convert existing to USD first, then to CSV currency
                                        existing_exchange_rate_used = existing_exchange_rate if existing_exchange_rate else 1.0
                                        existing_price_usd_calc = existing_price / existing_exchange_rate_used
                                        csv_exchange_rate = currency_service.rates.get(currency, 1.0)
                                        existing_price_in_csv_currency = existing_price_usd_calc * csv_exchange_rate
                                    elif existing_currency == 'USD' and currency != 'USD':
                                        csv_exchange_rate = currency_service.rates.get(currency, 1.0)
                                        existing_price_in_csv_currency = existing_price * csv_exchange_rate

                                # Weighted average: (existing * existing_price + new_buys * csv_price) / (existing + new_buys)
                                existing_value = existing_amount * existing_price_in_csv_currency
                                csv_buy_value = csv_buy_qty * csv_price
                                total_value = existing_value + csv_buy_value
                                total_quantity_for_price = existing_amount + csv_buy_qty
                                merged_price = total_value / total_quantity_for_price if total_quantity_for_price > 0 else existing_price

                                # Calculate USD prices
                                if currency != 'USD':
                                    csv_exchange_rate = currency_service.rates.get(currency, 1.0)
                                    csv_price_usd = csv_price / csv_exchange_rate
                                else:
                                    csv_exchange_rate = None
                                    csv_price_usd = csv_price

                                # Merge commission (only from buys, not sells)
                                merged_commission = existing_commission + item.get('fees', 0)
                                
                                if existing_price_usd:
                                    existing_value_usd = existing_amount * existing_price_usd
                                else:
                                    existing_value_usd = existing_amount * csv_price_usd  # Fallback

                                csv_buy_value_usd = csv_buy_qty * csv_price_usd
                                total_value_usd = existing_value_usd + csv_buy_value_usd
                                merged_price_usd = total_value_usd / total_quantity_for_price if total_quantity_for_price > 0 else (existing_price_usd or csv_price_usd)
                                
                                if currency != 'USD':
                                    merged_commission_usd = existing_commission_usd + (item.get('fees', 0) / csv_exchange_rate)
                                    merged_exchange_rate = csv_exchange_rate
                                else:
                                    merged_commission_usd = existing_commission_usd + item.get('fees', 0)
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

                        # Calculate total investment for display
                        if currency != 'USD':
                            exchange_rate_for_display = currency_service.rates.get(currency, 1.0)
                            total_investment_usd = (new_amount * merged_price_usd) + merged_commission_usd
                            total_investment = total_investment_usd * exchange_rate_for_display
                        else:
                            total_investment = (new_amount * merged_price) + merged_commission

                        currency_symbols = {'USD': '$', 'EUR': '€', 'CZK': 'Kč', 'GBP': '£', 'JPY': '¥'}
                        currency_symbol = currency_symbols.get(currency, currency + ' ')
                        total_investment_text = f"{currency_symbol}{total_investment:.2f}"

                        # Update portfolio item
                        update_sql = _normalize_placeholders(
                            "UPDATE portfolio_items SET "
                            "amount = ?, price_buy = ?, commission = ?, "
                            "price_buy_usd = ?, commission_usd = ?, exchange_rate_at_purchase = ?, "
                            "total_investment_text = ?, updated_at = ?, source = ? "
                            "WHERE id = ? AND user_id = ?",
                            is_pg
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
                    if net_change > 0:
                        # Insert new item (net change is positive = buy)
                        if currency != 'USD':
                            exchange_rate = currency_service.rates.get(currency, 1.0)
                            price_usd = item['price'] / exchange_rate
                            fees_usd = item['fees'] / exchange_rate if item['fees'] > 0 else 0.0
                            value_usd = item.get('value', 0) / exchange_rate if item.get('value', 0) > 0 else 0.0
                        else:
                            exchange_rate = None
                            price_usd = item['price']
                            fees_usd = item['fees']
                            value_usd = item.get('value', 0)

                        if item.get('value', 0) > 0:
                            total_investment = item['value'] + item['fees']
                        else:
                            total_investment = item['quantity'] * item['price'] + item['fees']

                        currency_symbols = {'USD': '$', 'EUR': '€', 'CZK': 'Kč', 'GBP': '£', 'JPY': '¥'}
                        currency_symbol = currency_symbols.get(currency, currency + ' ')
                        total_investment_text = f"{currency_symbol}{total_investment:.2f}"

                        insert_sql = _normalize_placeholders(
                            "INSERT INTO portfolio_items "
                            "(user_id, symbol, amount, price_buy, purchase_date, base_currency, source, commission, "
                            "total_investment_text, created_at, updated_at, price_buy_usd, commission_usd, exchange_rate_at_purchase) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            is_pg
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

        if is_pg:
            # PostgreSQL: use ON CONFLICT DO UPDATE
            mapping_sql = (
                "INSERT INTO csv_import_mappings "
                "(user_id, exchange, column_mapping, created_at, updated_at, last_used) "
                "VALUES (%s, %s, %s, NOW(), NOW(), NOW()) "
                "ON CONFLICT (user_id, exchange) DO UPDATE SET "
                "column_mapping = EXCLUDED.column_mapping, updated_at = NOW(), last_used = NOW()"
            )
        else:
            # SQLite: use INSERT OR REPLACE
            mapping_sql = (
                "INSERT OR REPLACE INTO csv_import_mappings "
                "(user_id, exchange, column_mapping, created_at, updated_at, last_used) "
                "VALUES (?, ?, ?, datetime('now'), datetime('now'), datetime('now'))"
            )
        cursor.execute(mapping_sql, (current_user["id"], exchange.lower(), json.dumps(column_mapping_data)))

        total_processed = imported_count + updated_count + deleted_count
        history_sql = _normalize_placeholders(
            "INSERT INTO import_history "
            "(user_id, source, import_date, items_imported, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            is_pg
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
        is_pg = is_postgres_connection(conn)
        sql = _normalize_placeholders(
            "SELECT column_mapping FROM csv_import_mappings WHERE user_id = ? AND exchange = ?",
            is_pg
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
        is_pg = is_postgres_connection(conn)
        if is_pg:
            # PostgreSQL: use ON CONFLICT DO UPDATE
            sql = (
                "INSERT INTO csv_import_mappings "
                "(user_id, exchange, column_mapping, created_at, updated_at, last_used) "
                "VALUES (%s, %s, %s, NOW(), NOW(), NOW()) "
                "ON CONFLICT (user_id, exchange) DO UPDATE SET "
                "column_mapping = EXCLUDED.column_mapping, updated_at = NOW(), last_used = NOW()"
            )
        else:
            # SQLite: use INSERT OR REPLACE
            sql = (
                "INSERT OR REPLACE INTO csv_import_mappings "
                "(user_id, exchange, column_mapping, created_at, updated_at, last_used) "
                "VALUES (?, ?, ?, datetime('now'), datetime('now'), datetime('now'))"
            )
        cursor.execute(sql, (current_user["id"], exchange.lower(), json.dumps(mapping_data)))
        conn.commit()
        conn.close()
        return {'message': 'Mapping saved successfully'}
    except Exception as e:
        logger.error(f"Error saving CSV mapping: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save mapping: {str(e)}")

