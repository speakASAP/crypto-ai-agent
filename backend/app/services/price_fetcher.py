"""
Background Price Fetcher Service
Automatically fetches crypto prices and currency rates
"""
import asyncio
import logging
from typing import List, Dict
from app.services.price_service import PriceService
from app.services.currency_service import currency_service
from app.api.websocket import manager

logger = logging.getLogger(__name__)

class PriceFetcherService:
    def __init__(self, price_service: PriceService):
        self.price_service = price_service
        self.is_running = False
        self.fetch_interval = 30  # seconds
        self.tracked_symbols = set()
        
    async def start(self):
        """Start the background price fetching service"""
        if self.is_running:
            return
            
        self.is_running = True
        logger.info("🚀 Starting background price fetcher service")
        
        # Start background tasks
        asyncio.create_task(self._price_fetch_loop())
        asyncio.create_task(self._currency_fetch_loop())
        
    async def stop(self):
        """Stop the background price fetching service"""
        self.is_running = False
        logger.info("🛑 Stopping background price fetcher service")
        
    async def add_tracked_symbols(self, symbols: List[str]):
        """Add symbols to track for price updates"""
        self.tracked_symbols.update(symbols)
        logger.info(f"📊 Added {len(symbols)} symbols to tracking: {symbols}")
        
    async def remove_tracked_symbols(self, symbols: List[str]):
        """Remove symbols from tracking"""
        self.tracked_symbols.difference_update(symbols)
        logger.info(f"📊 Removed {len(symbols)} symbols from tracking: {symbols}")
        
    async def _price_fetch_loop(self):
        """Background loop to fetch crypto prices"""
        while self.is_running:
            try:
                if self.tracked_symbols:
                    # Fetch prices for all tracked symbols
                    symbols_list = list(self.tracked_symbols)
                    prices = await self.price_service.get_current_prices(symbols_list)
                    
                    # Broadcast price updates via WebSocket
                    for symbol, price in prices.items():
                        await self._broadcast_price_update(symbol, price)
                        
                    logger.debug(f"📈 Fetched prices for {len(prices)} symbols")
                else:
                    logger.debug("📊 No symbols to track, skipping price fetch")
                    
            except Exception as e:
                logger.error(f"❌ Error in price fetch loop: {e}")
                
            # Wait before next fetch
            await asyncio.sleep(self.fetch_interval)
            
    async def _currency_fetch_loop(self):
        """Background loop to fetch currency rates"""
        while self.is_running:
            try:
                # Fetch currency rates every 30 minutes
                await currency_service.get_exchange_rates()
                logger.debug("💱 Currency rates updated")
                
            except Exception as e:
                logger.error(f"❌ Error in currency fetch loop: {e}")
                
            # Wait 30 minutes before next currency fetch
            await asyncio.sleep(1800)
            
    async def _broadcast_price_update(self, symbol: str, price: float):
        """Broadcast price update to all connected WebSocket clients"""
        try:
            import time
            message = {
                "type": "price_update",
                "data": {
                    "symbol": symbol,
                    "price": price,
                    "timestamp": time.time()
                }
            }
            import json
            await manager.broadcast(json.dumps(message))
            logger.debug(f"📡 Broadcasted price update for {symbol}: {price}")
            
        except Exception as e:
            logger.error(f"❌ Error broadcasting price update: {e}")

# Global price fetcher instance
price_fetcher = None

async def get_price_fetcher(price_service: PriceService) -> PriceFetcherService:
    """Get or create the global price fetcher instance"""
    global price_fetcher
    if price_fetcher is None:
        price_fetcher = PriceFetcherService(price_service)
    return price_fetcher
