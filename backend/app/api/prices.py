from datetime import datetime, timezone
from typing import List
import json
import ssl
import aiohttp
import asyncio

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies.auth import get_current_active_user, get_db_connection
from ..services.currency_service import currency_service
from ..services.price_service import PriceService
from ..services.multi_exchange_price_service import multi_exchange_price_service
from ..schemas.common import TrackedSymbol, CryptoSymbol
from pydantic import BaseModel
from .ws import manager
try:
    from utils.logger import get_logger
except Exception:  # pragma: no cover
    from ..utils.logger import get_logger

from ..utils.db import normalize_placeholders as _normalize_placeholders
from ..core.config import settings


router = APIRouter(tags=["prices", "symbols", "currency"])
logger = get_logger("backend.app.api.prices")
price_service = PriceService()


@router.get("/api/symbols/tracked", response_model=List[TrackedSymbol])
async def get_tracked_symbols(active_only: bool = False, current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    if active_only:
        sql = _normalize_placeholders("SELECT symbol, name, active, last_updated FROM tracked_symbols WHERE user_id = %s AND active = TRUE ORDER BY symbol")
        cursor.execute(sql, (current_user["id"],))
    else:
        sql = _normalize_placeholders("SELECT symbol, name, active, last_updated FROM tracked_symbols WHERE user_id = %s ORDER BY symbol")
        cursor.execute(sql, (current_user["id"],))
    rows = cursor.fetchall()
    conn.close()
    # Map database fields (symbol, name, active, last_updated) to frontend format (symbol, name, is_active, created_at)
    symbols = []
    for row in rows:
        # Convert datetime to ISO string if needed
        created_at = row[3]
        if hasattr(created_at, 'isoformat'):
            created_at = created_at.isoformat()
        elif isinstance(created_at, str):
            pass  # Already a string
        else:
            created_at = str(created_at)
        
        symbols.append(TrackedSymbol(
            symbol=row[0],
            name=row[1] if row[1] else row[0],
            is_active=bool(row[2]),
            created_at=created_at
        ))
    return symbols


class TrackedSymbolCreate(BaseModel):
    symbol: str
    name: str | None = None
    active: bool = True
    is_active: bool | None = None  # Support frontend format
    
    def __init__(self, **data):
        # Map is_active to active for compatibility
        if 'is_active' in data and 'active' not in data:
            data['active'] = data.pop('is_active', True)
        super().__init__(**data)


@router.post("/api/symbols/tracked", response_model=TrackedSymbol)
async def add_tracked_symbol(payload: TrackedSymbolCreate, current_user: dict = Depends(get_current_active_user)):
    """Add or activate a tracked symbol for the current user."""
    try:
        symbol = payload.symbol.strip().upper()
        name = (payload.name or symbol).strip()
        active = payload.active

        conn = get_db_connection()
        cursor = conn.cursor()

        now = datetime.now(timezone.utc).isoformat()

        sql = (
            "INSERT INTO tracked_symbols (user_id, symbol, name, active, last_updated) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (user_id, symbol) DO UPDATE SET name = EXCLUDED.name, active = EXCLUDED.active, last_updated = EXCLUDED.last_updated"
        )
        params = (current_user["id"], symbol, name, bool(active), now)
        cursor.execute(sql, params)
        conn.commit()
        conn.close()

        # Return in frontend format (is_active instead of active, created_at instead of last_updated)
        return TrackedSymbol(symbol=symbol, name=name, is_active=active, created_at=now)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding tracked symbol {payload.symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add tracked symbol: {str(e)}")


@router.get("/api/symbols/prices")
async def get_symbol_prices(symbols: str = None, current_user: dict = Depends(get_current_active_user)):
    """Get prices for symbols from centralized crypto_prices table, fetching from external APIs if missing"""
    try:
        if not symbols:
            return []
        symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        if not symbol_list:
            return []
        
        # Read prices from centralized crypto_prices table
        prices_from_db = price_service.get_prices_from_db(symbol_list)
        
        # Identify symbols that are missing from the database
        missing_symbols = [s for s in symbol_list if s not in prices_from_db]
        
        # Fetch missing prices from external APIs
        if missing_symbols:
            logger.info(f"Fetching prices for {len(missing_symbols)} missing symbols: {missing_symbols}")
            try:
                # Filter out fiat currencies - they're handled separately
                fiat_currencies = {'USDT', 'USD', 'EUR', 'GBP', 'JPY', 'CZK', 'USDC', 'BUSD', 'DAI', 'TUSD'}
                crypto_missing = [s for s in missing_symbols if s not in fiat_currencies]
                
                if crypto_missing:
                    # Fetch prices from external APIs
                    fetched_prices = await multi_exchange_price_service.get_current_prices(crypto_missing)
                    
                    # Store fetched prices in database for future use
                    if fetched_prices:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        
                        for symbol, price_usd in fetched_prices.items():
                            try:
                                # UPSERT: Insert or update price in crypto_prices table
                                upsert_sql = _normalize_placeholders(
                                    """
                                    INSERT INTO crypto_prices (symbol, price_usd, updated_at, created_at)
                                    VALUES (%s, %s, NOW(), COALESCE((SELECT created_at FROM crypto_prices WHERE symbol = %s), NOW()))
                                    ON CONFLICT (symbol) DO UPDATE SET
                                        price_usd = EXCLUDED.price_usd,
                                        updated_at = NOW()
                                    """
                                )
                                cursor.execute(upsert_sql, (symbol, price_usd, symbol))
                                # Add to prices_from_db so it's included in the result
                                prices_from_db[symbol] = price_usd
                                logger.debug(f"Stored fetched price for {symbol}: {price_usd}")
                            except Exception as e:
                                logger.error(f"Error storing price for {symbol}: {e}")
                                continue
                        
                        conn.commit()
                        conn.close()
                        logger.info(f"Successfully fetched and stored prices for {len(fetched_prices)} symbols")
                else:
                    logger.debug(f"All missing symbols are fiat currencies, skipping external API fetch")
            except Exception as e:
                logger.error(f"Error fetching missing prices from external APIs: {e}", exc_info=True)
                # Continue with what we have from database
        
        # Get timestamps for all symbols in one query
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join(['%s'] * len(symbol_list))
        sql = _normalize_placeholders(
            f"SELECT symbol, updated_at FROM crypto_prices WHERE symbol IN ({placeholders})"
        )
        cursor.execute(sql, symbol_list)
        timestamp_rows = cursor.fetchall()
        conn.close()
        
        # Create timestamp map
        timestamp_map = {}
        for row in timestamp_rows:
            symbol, updated_at = row
            if updated_at:
                if isinstance(updated_at, datetime):
                    timestamp_map[symbol] = updated_at.isoformat()
                else:
                    timestamp_map[symbol] = str(updated_at)
        
        result = []
        current_timestamp = datetime.now(timezone.utc).isoformat()
        for symbol in symbol_list:
            if symbol in prices_from_db:
                price = prices_from_db[symbol]
                timestamp = timestamp_map.get(symbol, current_timestamp)
                result.append({"symbol": symbol, "price": price, "timestamp": timestamp})
            else:
                # Price still not found after fetching - return with null price
                logger.warning(f"Price not found for {symbol} even after external API fetch")
                result.append({"symbol": symbol, "price": None, "timestamp": None})
        
        return result
    except Exception as e:
        logger.error(f"Error fetching prices from database: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch prices")


@router.get("/api/symbols/{symbol}/price")
async def get_symbol_price(symbol: str, current_user: dict = Depends(get_current_active_user)):
    """Get price for a symbol from centralized crypto_prices table"""
    try:
        symbol_upper = symbol.upper()
        
        # Read price from centralized crypto_prices table
        price = price_service.get_price_from_db(symbol_upper)
        
        if price is not None:
            # Get timestamp from database
            conn = get_db_connection()
            cursor = conn.cursor()
            sql = _normalize_placeholders(
                "SELECT updated_at FROM crypto_prices WHERE symbol = %s"
            )
            cursor.execute(sql, (symbol_upper,))
            row = cursor.fetchone()
            conn.close()
            
            timestamp = datetime.now(timezone.utc).isoformat()
            if row and row[0]:
                if isinstance(row[0], datetime):
                    timestamp = row[0].isoformat()
                else:
                    timestamp = str(row[0])
            
            return {"symbol": symbol_upper, "price": price, "timestamp": timestamp}
        else:
            logger.warning(f"Price not found in database for symbol {symbol_upper}")
            raise HTTPException(status_code=404, detail=f"Price not found for symbol {symbol}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch price")


@router.post("/api/currency/refresh")
async def refresh_currency_rates():
    await currency_service.refresh_rates()
    return {
        "message": "Currency rates refreshed successfully",
        "rates_count": len(currency_service.rates),
        "last_updated": currency_service.last_updated_timestamp.isoformat() + "Z" if currency_service.last_updated_timestamp else currency_service.last_updated,
    }


@router.post("/api/crypto/refresh")
async def refresh_crypto_prices(current_user: dict = Depends(get_current_active_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM portfolio_items")
        portfolio_symbols = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT symbol FROM tracked_symbols WHERE active = TRUE")
        tracked_symbols = [row[0] for row in cursor.fetchall()]
        all_symbols = list(set(portfolio_symbols + tracked_symbols))
        conn.close()
        if not all_symbols:
            return {"message": "No symbols to refresh", "symbols_count": 0, "last_updated": datetime.now().isoformat() + "Z"}
        from ..services.price_tasks import fetch_prices_for_symbols  # lazy import to avoid cycle
        await fetch_prices_for_symbols(all_symbols)
        return {"message": "Crypto prices refreshed successfully", "symbols_count": len(all_symbols), "symbols": all_symbols, "last_updated": datetime.now().isoformat() + "Z"}
    except Exception as e:
        logger.error(f"Error refreshing crypto prices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh crypto prices: {str(e)}")


@router.get("/api/currency/rates")
async def get_currency_rates():
    return {
        "base_currency": currency_service.base_currency,
        "rates": currency_service.rates,
        "last_updated": currency_service.last_updated,
        "last_updated_timestamp": currency_service.get_timestamp_iso(),
        "last_updated_formatted": currency_service.get_formatted_timestamp(),
    }


@router.get("/api/symbols/last-updated")
async def get_symbol_last_updated():
    return {
        "last_bulk_update": price_service.get_timestamp_iso(),
        "last_bulk_update_formatted": price_service.get_formatted_timestamp(),
        "symbol_timestamps": price_service.get_all_symbol_timestamps(),
    }


@router.get("/api/crypto-symbols", response_model=List[CryptoSymbol])
async def get_crypto_symbols(limit: int = 500, current_user: dict = Depends(get_current_active_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = _normalize_placeholders(
        """
        SELECT symbol, name, market_cap_rank, last_updated 
        FROM crypto_symbols 
        ORDER BY market_cap_rank ASC, symbol ASC 
        LIMIT %s
        """
    )
    cursor.execute(sql, (limit,))
    rows = cursor.fetchall()
    conn.close()
    symbols = [CryptoSymbol(symbol=row[0], name=row[1], market_cap_rank=row[2], last_updated=row[3]) for row in rows]
    return symbols


@router.get("/api/crypto-symbols/search", response_model=List[CryptoSymbol])
async def search_crypto_symbols(q: str, limit: int = 50, current_user: dict = Depends(get_current_active_user)):
    if not q or len(q) < 2:
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    search_term = f"%{q.upper()}%"
    sql = _normalize_placeholders(
        """
        SELECT symbol, name, market_cap_rank, last_updated 
        FROM crypto_symbols 
        WHERE symbol LIKE %s OR name LIKE %s
        ORDER BY market_cap_rank ASC, symbol ASC 
        LIMIT %s
        """
    )
    cursor.execute(sql, (search_term, search_term, limit))
    rows = cursor.fetchall()
    conn.close()
    symbols = [CryptoSymbol(symbol=row[0], name=row[1], market_cap_rank=row[2], last_updated=row[3]) for row in rows]
    return symbols


async def _refresh_crypto_symbols_helper():
    """Helper function to refresh crypto symbols without requiring authentication.
    This is used both by the API endpoint and by background tasks (e.g., after registration).
    Ensures at least 500 cryptos (2 pages) are fetched, including top cryptos like BTC, ETH.
    """
    try:
        logger.info("Starting crypto symbols refresh from CoinGecko API")
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            url = "https://api.coingecko.com/api/v3/coins/markets"
            all_data = []
            page_count = 0
            min_required_pages = 2  # Need at least 2 pages (500 coins)
            max_pages = 3  # Try to fetch up to 3 pages (750 coins)
            
            # Fetch multiple pages to get comprehensive coverage
            for page_num in range(1, max_pages + 1):
                params = {
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 250,
                    "page": page_num,
                    "sparkline": "false"
                }
                
                try:
                    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            data = await response.json()
                            if isinstance(data, list) and len(data) > 0:
                                all_data.extend(data)
                                page_count += 1
                                logger.info(f"Successfully fetched page {page_num}: {len(data)} coins")
                                
                                # Check if we have top cryptos in first page
                                if page_num == 1:
                                    first_page_symbols = [coin.get("symbol", "").upper() for coin in data]
                                    if "BTC" not in first_page_symbols:
                                        logger.error(f"⚠️ CRITICAL: BTC not found in first page! Symbols found: {first_page_symbols[:10]}")
                                    if "ETH" not in first_page_symbols:
                                        logger.warning(f"⚠️ ETH not found in first page!")
                            else:
                                logger.warning(f"Page {page_num} returned empty or invalid data")
                                if page_num < min_required_pages:
                                    raise HTTPException(status_code=500, detail=f"Page {page_num} returned empty data, but at least {min_required_pages} pages are required")
                                break  # No more data available
                        elif response.status == 429:
                            logger.warning(f"Rate limit hit on page {page_num}, waiting and retrying...")
                            await asyncio.sleep(5)  # Wait 5 seconds for rate limit
                            # Retry once
                            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as retry_response:
                                if retry_response.status == 200:
                                    data = await retry_response.json()
                                    if isinstance(data, list) and len(data) > 0:
                                        all_data.extend(data)
                                        page_count += 1
                                        logger.info(f"Successfully fetched page {page_num} on retry: {len(data)} coins")
                                    else:
                                        logger.warning(f"Page {page_num} returned empty on retry")
                                        if page_num < min_required_pages:
                                            raise HTTPException(status_code=500, detail=f"Page {page_num} returned empty on retry")
                                        break
                                else:
                                    error_text = await retry_response.text()
                                    logger.error(f"Retry failed for page {page_num}: {retry_response.status} - {error_text[:200]}")
                                    if page_num < min_required_pages:
                                        raise HTTPException(status_code=500, detail=f"Failed to fetch required page {page_num}")
                                    break
                        else:
                            error_text = await response.text()
                            logger.error(f"Failed to fetch page {page_num}: HTTP {response.status} - {error_text[:200]}")
                            if page_num < min_required_pages:
                                # Required page failure is critical
                                raise HTTPException(status_code=500, detail=f"Failed to fetch required page {page_num} from CoinGecko API: {response.status}")
                            # For optional pages, continue with what we have
                            break
                except asyncio.TimeoutError:
                    logger.error(f"Timeout fetching page {page_num}")
                    if page_num < min_required_pages:
                        raise HTTPException(status_code=500, detail=f"Timeout fetching required page {page_num}")
                    break
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Error fetching page {page_num}: {e}", exc_info=True)
                    if page_num < min_required_pages:
                        raise HTTPException(status_code=500, detail=f"Error fetching required page {page_num}: {str(e)}")
                    break
                
                # Small delay between pages to avoid rate limiting
                if page_num < max_pages:
                    await asyncio.sleep(1)
            
            if not all_data:
                logger.error("No data fetched from CoinGecko API")
                raise HTTPException(status_code=500, detail="No data received from CoinGecko API")
            
            if len(all_data) < 250:
                logger.error(f"⚠️ CRITICAL: Only {len(all_data)} coins fetched, expected at least 250 from first page!")
                raise HTTPException(status_code=500, detail=f"Insufficient data fetched: only {len(all_data)} coins")
            
            logger.info(f"Total coins fetched: {len(all_data)} across {page_count} pages")
            
            # Process and insert into database
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Clear table before refresh
            cursor.execute("DELETE FROM crypto_symbols")
            logger.info("Cleared existing crypto_symbols table")
            
            current_time = datetime.now(timezone.utc).isoformat()
            inserted_count = 0
            skipped_count = 0
            error_count = 0
            top_cryptos_to_check = {"BTC": False, "ETH": False, "USDT": False, "BNB": False, "SOL": False}
            inserted_symbols = []
            
            # Track symbols we've seen to handle duplicates (keep the one with best rank)
            symbol_map = {}  # symbol -> (name, market_cap_rank, coin_data)
            
            # First pass: collect all coins and resolve duplicates by keeping best rank
            for coin in all_data:
                try:
                    symbol = str(coin.get("symbol", "")).upper()
                    name = str(coin.get("name", ""))
                    market_cap_rank = coin.get("market_cap_rank")
                    
                    # Validate required fields
                    if not symbol or not name:
                        skipped_count += 1
                        continue
                    
                    # Validate and convert market_cap_rank
                    try:
                        market_cap_rank = int(market_cap_rank) if market_cap_rank is not None else None
                    except (ValueError, TypeError):
                        market_cap_rank = None
                    
                    # Handle duplicates: keep the entry with the best (lowest) market_cap_rank
                    if symbol in symbol_map:
                        existing_rank = symbol_map[symbol][1]
                        # If new entry has better rank (lower number), or existing has no rank, replace it
                        if market_cap_rank is not None:
                            if existing_rank is None or market_cap_rank < existing_rank:
                                symbol_map[symbol] = (name, market_cap_rank, coin)
                                logger.debug(f"Replacing {symbol} entry: rank {existing_rank} -> {market_cap_rank}")
                        # If new entry has no rank but existing has rank, keep existing
                        elif existing_rank is None:
                            # Both have no rank, keep the first one
                            pass
                    else:
                        symbol_map[symbol] = (name, market_cap_rank, coin)
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing coin {coin.get('symbol', 'unknown')}: {e}", exc_info=True)
                    continue
            
            logger.info(f"Processed {len(all_data)} coins, resolved to {len(symbol_map)} unique symbols")
            
            # Second pass: insert resolved symbols into database
            for symbol, (name, market_cap_rank, coin) in symbol_map.items():
                try:
                    # Track top cryptos
                    if symbol in top_cryptos_to_check:
                        top_cryptos_to_check[symbol] = True
                        if symbol == "BTC" and market_cap_rank != 1:
                            logger.warning(f"⚠️ BTC found with rank {market_cap_rank}, expected 1")
                    
                    current_time_str = str(current_time)
                    
                    # Upsert to handle duplicate symbols across pages
                    sql = (
                        "INSERT INTO crypto_symbols (symbol, name, market_cap_rank, last_updated, created_at) "
                        "VALUES (%s, %s, %s, %s, %s) "
                        "ON CONFLICT (symbol) DO UPDATE SET "
                        "name = EXCLUDED.name, market_cap_rank = EXCLUDED.market_cap_rank, last_updated = EXCLUDED.last_updated, created_at = EXCLUDED.created_at"
                    )
                    cursor.execute(sql, (symbol, name, market_cap_rank, current_time_str, current_time_str))
                    
                    inserted_count += 1
                    inserted_symbols.append(symbol)
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error inserting coin {symbol}: {e}", exc_info=True)
                    try:
                        conn.rollback()
                    except:
                        pass
                    continue
            
            # Commit transaction
            conn.commit()
            
            # Verify top cryptos are in database
            logger.info(f"Successfully inserted {inserted_count} cryptocurrency symbols (skipped: {skipped_count}, errors: {error_count})")
            
            # Check if top cryptos were inserted
            missing_top_cryptos = [symbol for symbol, found in top_cryptos_to_check.items() if not found]
            if missing_top_cryptos:
                logger.error(f"⚠️ CRITICAL: Top cryptos missing: {missing_top_cryptos}")
                logger.error(f"Sample of inserted symbols: {inserted_symbols[:20]}")
            
            # Verify BTC is actually in database
            verify_sql = _normalize_placeholders("SELECT symbol FROM crypto_symbols WHERE symbol = %s")
            cursor.execute(verify_sql, ("BTC",))
            btc_in_db = cursor.fetchone() is not None
            
            if not btc_in_db:
                logger.error("⚠️ CRITICAL: BTC not found in database after insertion!")
                logger.error(f"Total symbols in DB: {inserted_count}")
                logger.error(f"Sample symbols: {inserted_symbols[:30]}")
            else:
                logger.info("✅ BTC verified in database")
            
            # Check total count
            count_sql = _normalize_placeholders("SELECT COUNT(*) FROM crypto_symbols")
            cursor.execute(count_sql)
            db_count = cursor.fetchone()[0]
            
            if db_count < 250:
                logger.warning(f"⚠️ Only {db_count} symbols in database, expected at least 250")
            
            conn.close()
            
            logger.info(f"✅ Crypto symbols refresh complete: {db_count} symbols in database")
            if btc_in_db:
                logger.info("✅ Top cryptos verified: BTC present")
            
            return inserted_count
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing crypto symbols: {e}", exc_info=True)
        raise


@router.post("/api/crypto-symbols/refresh")
async def refresh_crypto_symbols(current_user: dict = Depends(get_current_active_user)):
    """API endpoint to refresh crypto symbols (requires authentication)."""
    try:
        count = await _refresh_crypto_symbols_helper()
        return {
            "message": "Successfully refreshed cryptocurrency symbols",
            "count": count,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error refreshing crypto symbols: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh crypto symbols: {str(e)}")


