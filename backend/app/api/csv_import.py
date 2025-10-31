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
        now = datetime.now().isoformat() + "Z"

        for item in aggregated_items:
            try:
                check_duplicate_sql = _normalize_placeholders(
                    "SELECT id FROM portfolio_items WHERE user_id = ? AND symbol = ? AND ABS(amount - ?) < 0.001",
                    is_pg
                )
                cursor.execute(check_duplicate_sql, (current_user["id"], item['symbol'], item['quantity']))
                if cursor.fetchone():
                    logger.info(f"Skipping duplicate: {item['symbol']}")
                    continue

                currency = item.get('currency', 'USD')
                currency_service.ensure_rates_initialized()

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
                    current_user["id"], item['symbol'], item['quantity'], item['price'],
                    item['date'], currency, exchange.capitalize(), item['fees'],
                    total_investment_text, now, now, price_usd, fees_usd, exchange_rate,
                ))
                imported_count += 1
            except Exception as e:
                logger.warning(f"Failed to import item {item['symbol']}: {e}")
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

        history_sql = _normalize_placeholders(
            "INSERT INTO import_history "
            "(user_id, source, import_date, items_imported, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            is_pg
        )
        cursor.execute(history_sql, (current_user["id"], exchange.capitalize(), now, imported_count, 'success' if imported_count > 0 else 'partial', now))

        conn.commit()
        conn.close()

        logger.info(f"✅ CSV import completed: {imported_count} items imported for user {current_user['id']}")

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

        return {
            'success': True,
            'message': f'Successfully imported {imported_count} portfolio items from CSV',
            'items_imported': imported_count,
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

