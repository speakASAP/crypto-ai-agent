from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
from dotenv import load_dotenv
from .core.config import settings
try:
    from utils.logger import get_logger  # root-level utils when available
except Exception:  # pragma: no cover
    from .utils.logger import get_logger  # fallback to app-local logger

# Load environment variables
load_dotenv()

# Centralized logger
logger = get_logger("backend.app.main")

# Import background tasks
from .services.price_tasks import background_price_fetcher, fetch_prices_for_symbols
from .services.ai_advisor_service import background_ai_advisor_updater, background_prediction_verifier
from .services.currency_service import background_currency_fetcher, currency_service
from .services.chart_tasks import background_chart_data_fetcher
from .services.notification_service import check_missed_alerts_on_startup
from .core.database import (
    verify_database_connection_and_schema,
    init_postgres_database,
    ensure_ai_advisor_tables,
    ensure_comments_column,
    ensure_price_buy_usd_mandatory,
    populate_initial_prices,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Ensure file handler is attached (uvicorn may have reconfigured logging)
    root_logger = logging.getLogger()
    from .utils.logger import _setup_file_handler
    file_handler = _setup_file_handler()
    if file_handler not in root_logger.handlers:
        root_logger.addHandler(file_handler)
        logger.info("✅ File handler re-attached to root logger")

    if not settings.database_url:
        logger.error("❌ DATABASE_URL environment variable is required. PostgreSQL database connection is mandatory.")
        raise ConnectionError("DATABASE_URL environment variable is required. PostgreSQL database connection is mandatory.")

    logger.info("🚀 Starting Crypto AI Agent API v2.0 (PostgreSQL Mode)")
    try:
        # Verify database is available before attempting initialization
        is_connected, schema_exists, has_data = verify_database_connection_and_schema()
        if not is_connected:
            logger.error("❌ Database is not available. Service will start but will fail health checks.")
            logger.error("❌ Deployment should verify database availability before switching traffic.")
        elif has_data:
            logger.info("✅ Database is available with customer data. No table creation needed.")
        else:
            # Only initialize if database is available but empty
            init_postgres_database()
        logger.info("✅ Database verification/initialization complete")
    except Exception as e:
        logger.error(f"❌ Database initialization failed during startup: {str(e)}")
        logger.error("❌ Service will start but will fail health checks until database is available.")
        logger.error("❌ Deployment scripts should verify database before switching traffic.")
        # Continue startup - but health checks will fail until database is available

    # Ensure AI advisor tables exist
    ensure_ai_advisor_tables()
    logger.info("✅ AI advisor tables migration check complete")

    # Ensure comments column exists in portfolio_items table
    ensure_comments_column()
    logger.info("✅ Portfolio items comments column migration check complete")

    # Ensure price_buy_usd is mandatory (NOT NULL) in portfolio_items table
    ensure_price_buy_usd_mandatory()
    logger.info("✅ Portfolio items price_buy_usd mandatory constraint check complete")

    # Populate initial prices in crypto_prices table if empty
    await populate_initial_prices()
    logger.info("✅ Initial price population check complete")

    # Initialize currency service
    await currency_service.get_exchange_rates()
    logger.info("✅ Currency service initialized")

    # Check for missed alerts on startup
    await check_missed_alerts_on_startup()
    logger.info("✅ Missed alert check completed")

    # Start background price update task
    price_task = asyncio.create_task(background_price_fetcher())
    logger.info("✅ Price update task started")

    # Start background currency update task
    currency_task = asyncio.create_task(background_currency_fetcher())
    logger.info("✅ Currency update task started")

    # Start background AI advisor update task
    ai_advisor_task = asyncio.create_task(background_ai_advisor_updater())
    logger.info("✅ AI advisor update task started")

    # Start background prediction verification task
    prediction_verifier_task = asyncio.create_task(background_prediction_verifier())
    logger.info("✅ Prediction verification task started")

    # Start background chart data fetcher (hourly updates)
    chart_task = asyncio.create_task(background_chart_data_fetcher())
    logger.info("✅ Chart data fetcher task started (hourly updates)")

    yield

    # Shutdown
    price_task.cancel()
    currency_task.cancel()
    try:
        ai_advisor_task.cancel()
        prediction_verifier_task.cancel()
        chart_task.cancel()
    except NameError:
        pass  # Tasks may not have been created if startup failed
    logger.info("🛑 Shutting down Crypto AI Agent API v2.0")

# Create FastAPI app
app = FastAPI(
    title="Crypto AI Agent API",
    description="Advanced cryptocurrency portfolio management API",
    version="2.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Import routers
from .api.auth import router as auth_router
app.include_router(auth_router)

# Logging endpoints (for frontend logs)
from .api.logging import router as logging_router
app.include_router(logging_router)

# Portfolio endpoints
from .api.portfolio import router as portfolio_router
app.include_router(portfolio_router)

from .api.alerts import router as alerts_router
app.include_router(alerts_router)

from .api.prices import router as prices_router
app.include_router(prices_router)

from .api.csv_import import router as csv_import_router
app.include_router(csv_import_router)

from .api.exchange_imports import router as exchange_imports_router
app.include_router(exchange_imports_router)

from .api.ws import router as ws_router
app.include_router(ws_router)

# All endpoints have been moved to modular routers in app/api/
# Import endpoints: app/api/exchange_imports.py
# CSV import endpoints: app/api/csv_import.py

from .api.health import router as health_router
app.include_router(health_router)

from .api.ai_advisor import router as ai_advisor_router
app.include_router(ai_advisor_router)

from .api.charts import router as charts_router
app.include_router(charts_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
