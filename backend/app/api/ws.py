from typing import List, Dict, Set
from datetime import datetime, timezone
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
try:
    from utils.logger import get_logger
except Exception:  # pragma: no cover
    from ..utils.logger import get_logger


router = APIRouter(tags=["websocket"])
logger = get_logger("backend.app.api.ws")


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.price_subscribers: Dict[str, Set[WebSocket]] = {}
        self.alert_subscribers: Set[WebSocket] = set()
        self.price_cache: Dict[str, Dict] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        for symbol, subscribers in self.price_subscribers.items():
            subscribers.discard(websocket)
        self.alert_subscribers.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections.copy():
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                self.disconnect(connection)

    async def send_price_update(self, symbol: str, price: float):
        current_time = datetime.now(timezone.utc)
        message = json.dumps({
            "type": "price_update",
            "data": {
                "symbol": symbol,
                "price": price,
                "timestamp": current_time.isoformat(),
                "timestamp_formatted": current_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            },
        })
        if symbol in self.price_subscribers:
            for connection in self.price_subscribers[symbol].copy():
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error sending price update: {e}")
                    self.disconnect(connection)

    async def broadcast_price_update(self, symbol: str, price: float):
        await self.send_price_update(symbol, price)

    async def send_alert_triggered(self, alert_data: dict):
        message = json.dumps({
            "type": "alert_triggered",
            "data": {"alert": alert_data, "timestamp": datetime.now().isoformat()},
        })
        for connection in self.alert_subscribers.copy():
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending alert: {e}")
                self.disconnect(connection)

    def subscribe_to_prices(self, websocket: WebSocket, symbols: List[str]):
        for symbol in symbols:
            if symbol not in self.price_subscribers:
                self.price_subscribers[symbol] = set()
            self.price_subscribers[symbol].add(websocket)
        logger.info(f"Subscribed to price updates for: {symbols}")

    def subscribe_to_alerts(self, websocket: WebSocket):
        self.alert_subscribers.add(websocket)
        logger.info("Subscribed to alert notifications")


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)

                if message.get("type") == "subscribe":
                    symbols = message.get("symbols", [])
                    manager.subscribe_to_prices(websocket, symbols)
                    await manager.send_personal_message(json.dumps({
                        "type": "connection_status",
                        "data": f"Subscribed to {len(symbols)} symbols"
                    }), websocket)

                elif message.get("type") == "subscribe_alerts":
                    manager.subscribe_to_alerts(websocket)
                    await manager.send_personal_message(json.dumps({
                        "type": "connection_status",
                        "data": "Subscribed to alert notifications"
                    }), websocket)

            except asyncio.TimeoutError:
                try:
                    await manager.send_personal_message(json.dumps({
                        "type": "ping",
                        "data": "Connection alive"
                    }), websocket)
                except:
                    break

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

