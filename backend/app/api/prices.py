from datetime import datetime, timezone
from typing import List
import json
import ssl
import aiohttp

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies.auth import get_current_active_user, get_db_connection
from ..services.currency_service import currency_service
from ..services.price_service import PriceService
from ..services.multi_exchange_price_service import multi_exchange_price_service
from ..schemas.common import TrackedSymbol, CryptoSymbol
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
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
    if active_only:
        # Use correct boolean literal for each DB
        sql_text = "SELECT symbol, name, active, last_updated FROM tracked_symbols WHERE user_id = ? AND active = TRUE ORDER BY symbol" if is_pg else "SELECT symbol, name, active, last_updated FROM tracked_symbols WHERE user_id = ? AND active = 1 ORDER BY symbol"
        sql = _normalize_placeholders(sql_text, is_pg)
        cursor.execute(sql, (current_user["id"],))
    else:
        sql = _normalize_placeholders("SELECT symbol, name, active, last_updated FROM tracked_symbols WHERE user_id = ? ORDER BY symbol", is_pg)
        cursor.execute(sql, (current_user["id"],))
    rows = cursor.fetchall()
    conn.close()
    symbols = [TrackedSymbol(symbol=row[0], name=row[1], active=bool(row[2]), last_updated=row[3]) for row in rows]
    return symbols


@router.get("/api/symbols/prices")
async def get_symbol_prices(symbols: str = None, current_user: dict = Depends(get_current_active_user)):
    try:
        if not symbols:
            return []
        symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        if not symbol_list:
            return []
        result = []
        missing: List[str] = []
        # Return cached first, track missing
        for symbol in symbol_list:
            if symbol in manager.price_cache:
                cache_entry = manager.price_cache[symbol]
                result.append({"symbol": symbol, "price": cache_entry["price"], "timestamp": cache_entry["timestamp"]})
            else:
                missing.append(symbol)
        # Fetch missing prices and cache
        if missing:
            try:
                fetched = await multi_exchange_price_service.get_current_prices(missing)
                for sym in missing:
                    if sym in fetched:
                        price = fetched[sym]
                        ts = datetime.now(timezone.utc).isoformat()
                        manager.price_cache[sym] = {"price": price, "timestamp": ts}
                        result.append({"symbol": sym, "price": price, "timestamp": ts})
            except Exception as fe:
                logger.error(f"Error fetching prices for {missing}: {fe}")
        # Keep response aligned to requested order
        ordered = {r["symbol"]: r for r in result}
        return [ordered[s] for s in symbol_list if s in ordered]
    except Exception as e:
        logger.error(f"Error fetching cached prices: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch prices")


@router.get("/api/symbols/{symbol}/price")
async def get_symbol_price(symbol: str, current_user: dict = Depends(get_current_active_user)):
    try:
        prices = await multi_exchange_price_service.get_current_prices([symbol.upper()])
        if symbol.upper() in prices:
            return {"symbol": symbol.upper(), "price": prices[symbol.upper()], "timestamp": datetime.now(timezone.utc).isoformat()}
        else:
            logger.warning(f"Price not found for symbol {symbol.upper()}")
            raise HTTPException(status_code=404, detail=f"Price not found for symbol {symbol}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
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
        cursor.execute("SELECT symbol FROM tracked_symbols WHERE active = 1")
        tracked_symbols = [row[0] for row in cursor.fetchall()]
        all_symbols = list(set(portfolio_symbols + tracked_symbols))
        conn.close()
        if not all_symbols:
            return {"message": "No symbols to refresh", "symbols_count": 0, "last_updated": datetime.now().isoformat() + "Z"}
        from ..main import fetch_prices_for_symbols  # lazy import to avoid cycle
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
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
    sql = _normalize_placeholders(
        """
        SELECT symbol, name, market_cap_rank, last_updated 
        FROM crypto_symbols 
        ORDER BY market_cap_rank ASC, symbol ASC 
        LIMIT ?
        """,
        is_pg,
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
    is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
    search_term = f"%{q.upper()}%"
    sql = _normalize_placeholders(
        """
        SELECT symbol, name, market_cap_rank, last_updated 
        FROM crypto_symbols 
        WHERE symbol LIKE ? OR name LIKE ?
        ORDER BY market_cap_rank ASC, symbol ASC 
        LIMIT ?
        """,
        is_pg,
    )
    cursor.execute(sql, (search_term, search_term, limit))
    rows = cursor.fetchall()
    conn.close()
    symbols = [CryptoSymbol(symbol=row[0], name=row[1], market_cap_rank=row[2], last_updated=row[3]) for row in rows]
    return symbols


async def _refresh_crypto_symbols_helper():
    """Helper function to refresh crypto symbols without requiring authentication.
    This is used both by the API endpoint and by background tasks (e.g., after registration).
    """
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            url = "https://api.coingecko.com/api/v3/coins/markets"
            all_data = []
            params_page1 = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": 1, "sparkline": "false"}
            async with session.get(url, params=params_page1) as response:
                if response.status == 200:
                    data_page1 = await response.json()
                    all_data.extend(data_page1)
                else:
                    logger.error(f"Failed to fetch first page from CoinGecko API: {response.status}")
                    return
            params_page2 = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": 2, "sparkline": "false"}
            async with session.get(url, params=params_page2) as response:
                if response.status == 200:
                    data_page2 = await response.json()
                    all_data.extend(data_page2)
                else:
                    logger.warning(f"Failed to fetch second page from CoinGecko API: {response.status}, proceeding with first page")

            # Optional third page to improve coverage when rate limits allow
            params_page3 = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": 3, "sparkline": "false"}
            async with session.get(url, params=params_page3) as response:
                if response.status == 200:
                    data_page3 = await response.json()
                    all_data.extend(data_page3)
                else:
                    logger.warning("Third page fetch from CoinGecko failed or limited; proceeding with available data")

            data = all_data
            conn = get_db_connection()
            cursor = conn.cursor()
            is_pg = (getattr(settings, "environment", "development").lower() == "production") or bool(getattr(settings, "database_url", None))
            # Clear table before refresh
            cursor.execute("DELETE FROM crypto_symbols")
            current_time = datetime.now(timezone.utc).isoformat()
            inserted_count = 0
            for coin in data:
                try:
                    symbol = str(coin.get("symbol", "")).upper()
                    name = str(coin.get("name", ""))
                    market_cap_rank = coin.get("market_cap_rank")
                    if not symbol or not name:
                        continue
                    try:
                        market_cap_rank = int(market_cap_rank) if market_cap_rank is not None else None
                    except (ValueError, TypeError):
                        market_cap_rank = None
                    current_time_str = str(current_time)
                    if is_pg:
                        # Upsert to handle duplicate symbols across pages without aborting transaction
                        sql = (
                            "INSERT INTO crypto_symbols (symbol, name, market_cap_rank, last_updated, created_at) "
                            "VALUES (%s, %s, %s, %s, %s) "
                            "ON CONFLICT (symbol) DO UPDATE SET "
                            "name = EXCLUDED.name, market_cap_rank = EXCLUDED.market_cap_rank, last_updated = EXCLUDED.last_updated, created_at = EXCLUDED.created_at"
                        )
                        cursor.execute(sql, (symbol, name, market_cap_rank, current_time_str, current_time_str))
                    else:
                        sql = (
                            """
                            INSERT OR REPLACE INTO crypto_symbols (symbol, name, market_cap_rank, last_updated, created_at)
                            VALUES (?, ?, ?, ?, ?)
                            """
                        )
                        cursor.execute(sql, (symbol, name, market_cap_rank, current_time_str, current_time_str))
                    inserted_count += 1
                except Exception as e:
                    logger.error(f"Error inserting coin {coin.get('symbol', 'unknown')}: {e}")
                    # In Postgres, ensure we clear error state and continue
                    if is_pg:
                        conn.rollback()
                        # Restart a new transaction implicitly by continuing inserts
                    continue
            conn.commit()
            conn.close()
            logger.info(f"Successfully refreshed {inserted_count} cryptocurrency symbols")
    except Exception as e:
        logger.error(f"Error refreshing crypto symbols: {e}", exc_info=True)


@router.post("/api/crypto-symbols/refresh")
async def refresh_crypto_symbols(current_user: dict = Depends(get_current_active_user)):
    """API endpoint to refresh crypto symbols (requires authentication)."""
    try:
        await _refresh_crypto_symbols_helper()
        return {"message": "Successfully refreshed cryptocurrency symbols", "last_updated": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error(f"Error refreshing crypto symbols: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh crypto symbols: {str(e)}")


