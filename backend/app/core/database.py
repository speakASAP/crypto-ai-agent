"""Database initialization and migration functions"""
from ..utils.db import (
    normalize_placeholders as _normalize_placeholders,
    connect_with_retry,
    get_db_connection,
)
from ..services.multi_exchange_price_service import multi_exchange_price_service
from ..core.config import settings
try:
    from utils.logger import get_logger
except Exception:  # pragma: no cover
    from ..utils.logger import get_logger

logger = get_logger("backend.app.core.database")


def verify_database_connection_and_schema():
    """
    Verify database connection and check if schema already exists.
    Returns (is_connected, schema_exists, has_data)
    """
    try:
        conn = connect_with_retry(max_retries=3, initial_delay=1.0, max_delay=5.0, is_startup=False)
        cur = conn.cursor()

        # Check if users table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'users'
            );
        """)
        schema_exists = cur.fetchone()[0]

        # If schema exists, check if there's data
        has_data = False
        if schema_exists:
            cur.execute("SELECT COUNT(*) FROM users")
            user_count = cur.fetchone()[0]
            has_data = user_count > 0
            logger.info(f"✅ Database schema exists with {user_count} users")

        cur.close()
        conn.close()
        return True, schema_exists, has_data
    except Exception as e:
        logger.error(f"❌ Database verification failed: {str(e)}")
        return False, False, False


def init_postgres_database():
    """Initialize PostgreSQL database schema with retry logic.
    NEVER creates tables if database is not available or if schema already exists with data.
    """
    logger.info("🔄 Verifying database connection and schema...")

    # First, verify database is available
    is_connected, schema_exists, has_data = verify_database_connection_and_schema()

    if not is_connected:
        error_msg = "❌ Database is not available. Cannot initialize schema. Aborting table creation."
        logger.error(error_msg)
        raise ConnectionError(error_msg)

    if schema_exists and has_data:
        logger.info("✅ Database schema already exists with customer data. Skipping table creation.")
        logger.info("⚠️ NEVER create tables when database has existing customer data.")
        return  # Schema exists with data - do NOT create tables

    if schema_exists and not has_data:
        logger.info("⚠️ Database schema exists but is empty. Skipping table creation (tables may be created by migration).")
        return  # Schema exists but empty - might be a fresh database, but safer to skip

    # Only create tables if schema doesn't exist at all (new database)
    logger.info("📋 Database schema does not exist. Creating tables...")
    try:
        # Use retry logic for startup (max 5 retries, exponential backoff)
        conn = connect_with_retry(max_retries=5, initial_delay=2.0, max_delay=30.0, is_startup=True)
        cur = conn.cursor()

        # Create users table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            full_name TEXT,
            preferred_currency TEXT DEFAULT 'USD',
            is_active BOOLEAN DEFAULT TRUE,
            is_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            telegram_bot_token TEXT,
            telegram_chat_id TEXT,
            default_alert_percentage_above REAL DEFAULT 0.10,
            default_alert_percentage_below REAL DEFAULT 0.10
        )
        ''')

        # Create password reset tokens table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create user sessions table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

        # Create portfolio_items table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            symbol TEXT NOT NULL,
            amount REAL NOT NULL,
            price_buy REAL NOT NULL,
            purchase_date TIMESTAMP,
            base_currency TEXT NOT NULL,
            purchase_price_eur REAL,
            purchase_price_czk REAL,
            source TEXT,
            commission REAL DEFAULT 0.0,
            total_investment_text TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            current_price REAL,
            current_value REAL,
            pnl REAL,
            pnl_percent REAL,
            price_buy_usd REAL,
            commission_usd REAL,
            current_price_usd REAL,
            current_value_usd REAL,
            pnl_usd REAL,
            pnl_percent_usd REAL,
            exchange_rate_at_purchase REAL,
            comments TEXT
        )
    ''')
        # Add comments column if it doesn't exist (for existing databases)
        try:
            cur.execute('ALTER TABLE portfolio_items ADD COLUMN comments TEXT')
        except Exception:
            pass  # Column already exists

        # Create alerts table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            symbol TEXT NOT NULL,
            threshold_price REAL NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

        # Ensure alerts.id has a working sequence and default nextval (simple, robust approach)
        cur.execute("""
            CREATE SEQUENCE IF NOT EXISTS alerts_id_seq;
        """)
        cur.execute("""
            ALTER TABLE alerts ALTER COLUMN id SET DEFAULT nextval('alerts_id_seq');
        """)
        cur.execute("""
            SELECT setval('alerts_id_seq', COALESCE((SELECT MAX(id) FROM alerts), 0) + 1, false);
        """)

        # Create tracked_symbols table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS tracked_symbols (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            active BOOLEAN DEFAULT TRUE,
            last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, symbol)
        )
    ''')

        # Create alert_history table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS alert_history (
            id SERIAL PRIMARY KEY,
            alert_id INTEGER REFERENCES alerts(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            triggered_price REAL NOT NULL,
            triggered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            was_missed BOOLEAN DEFAULT FALSE,
            check_type TEXT DEFAULT 'realtime'
        )
    ''')

        # Create price_check_tracking table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS price_check_tracking (
            symbol TEXT PRIMARY KEY,
            last_check_timestamp TEXT NOT NULL,
            last_check_price REAL NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

        # Create import_history table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS import_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            source TEXT NOT NULL,
            import_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            items_imported INTEGER NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

        # Create currency_rates table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS currency_rates (
            id SERIAL PRIMARY KEY,
            from_currency TEXT NOT NULL,
            to_currency TEXT NOT NULL,
            rate REAL NOT NULL,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

        # Create crypto_symbols table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS crypto_symbols (
            id SERIAL PRIMARY KEY,
            symbol TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            market_cap_rank INTEGER,
            last_updated TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

        # Create user_api_credentials table (encrypted storage)
        cur.execute('''
        CREATE TABLE IF NOT EXISTS user_api_credentials (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            exchange TEXT NOT NULL,
            encrypted_credentials TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, exchange)
        )
    ''')

        # Create csv_import_mappings table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS csv_import_mappings (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            exchange TEXT NOT NULL,
            column_mapping TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP,
            UNIQUE(user_id, exchange)
        )
    ''')

        # Create ai_predictions table (user_id nullable for global predictions)
        cur.execute('''
        CREATE TABLE IF NOT EXISTS ai_predictions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            symbol TEXT NOT NULL,
            prediction_type TEXT NOT NULL,
            predicted_price REAL NOT NULL,
            confidence_percent REAL NOT NULL,
            prediction_reasoning TEXT,
            model_name TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            actual_price_at_target REAL,
            is_verified BOOLEAN DEFAULT FALSE,
            accuracy_percent REAL
        )
    ''')

        # Create index on ai_predictions for faster lookups
        cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_ai_predictions_symbol_created ON ai_predictions(symbol, created_at DESC)
    ''')

        # Create news_analysis table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS news_analysis (
            id SERIAL PRIMARY KEY,
            symbol TEXT NOT NULL,
            news_date TIMESTAMP NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            sentiment_score REAL,
            relevance_score REAL,
            source TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

        # Create price_history_cache table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS price_history_cache (
            symbol TEXT PRIMARY KEY,
            history_data TEXT NOT NULL,
            last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

        # Create crypto_prices table for centralized price storage
        cur.execute('''
        CREATE TABLE IF NOT EXISTS crypto_prices (
            symbol TEXT PRIMARY KEY,
            price_usd REAL NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

        # Create index on crypto_prices for faster lookups
        cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_crypto_prices_updated_at ON crypto_prices(updated_at)
    ''')

        conn.commit()
        conn.close()
        logger.info("✅ PostgreSQL schema initialized successfully with AI advisor tables and crypto_prices table")
    except Exception as e:
        logger.error(f"❌ Failed to initialize PostgreSQL database after retries: {str(e)}")
        logger.warning("⚠️ Database initialization failed, but continuing startup. Database might be ready later.")
        raise


def ensure_comments_column():
    """Ensure comments column exists in portfolio_items table.
    This function checks for missing column and adds it if needed,
    even if the table already exists (handles schema migrations).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # First check if portfolio_items table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'portfolio_items'
            )
        """)
        table_exists = cursor.fetchone()[0]

        if not table_exists:
            logger.debug("⚠️ portfolio_items table does not exist yet. Comments column will be added when table is created.")
            conn.close()
            return

        # Check if comments column exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'portfolio_items'
                AND column_name = 'comments'
            )
        """)
        column_exists = cursor.fetchone()[0]

        if not column_exists:
            logger.info("📋 Adding missing comments column to portfolio_items table...")
            cursor.execute("ALTER TABLE portfolio_items ADD COLUMN comments TEXT")
            conn.commit()
            logger.info("✅ Successfully added comments column to portfolio_items table")
        else:
            logger.debug("✅ comments column already exists in portfolio_items table")

        conn.close()
    except Exception as e:
        logger.error(f"❌ Error ensuring comments column: {e}", exc_info=True)
        # Don't raise - allow service to continue even if column addition fails
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def ensure_ai_advisor_tables():
    """Ensure ai_predictions and price_history_cache tables exist.
    This function checks for missing tables and creates them if needed,
    even if other tables already exist (handles partial schema scenarios).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        tables_created = []

        # Check and create ai_predictions table
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'ai_predictions'
            )
        """)
        ai_predictions_exists = cursor.fetchone()[0]

        if not ai_predictions_exists:
            logger.info("📋 Creating missing ai_predictions table...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_predictions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    symbol TEXT NOT NULL,
                    prediction_type TEXT NOT NULL,
                    predicted_price REAL NOT NULL,
                    confidence_percent REAL NOT NULL,
                    prediction_reasoning TEXT,
                    model_name TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    actual_price_at_target REAL,
                    is_verified BOOLEAN DEFAULT FALSE,
                    accuracy_percent REAL
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_ai_predictions_symbol_created ON ai_predictions(symbol, created_at DESC)
            ''')
            tables_created.append("ai_predictions")
        else:
            # Check if user_id column allows NULL (migration for existing tables)
            cursor.execute("""
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_name = 'ai_predictions' AND column_name = 'user_id'
            """)
            result = cursor.fetchone()
            if result and result[0] == 'NO':
                logger.info("📋 Migrating ai_predictions.user_id to allow NULL for global predictions...")
                try:
                    # Drop foreign key constraint if it exists
                    cursor.execute("""
                        SELECT constraint_name
                        FROM information_schema.table_constraints
                        WHERE table_name = 'ai_predictions'
                        AND constraint_type = 'FOREIGN KEY'
                        AND constraint_name LIKE '%user_id%'
                    """)
                    fk_result = cursor.fetchone()
                    if fk_result:
                        fk_name = fk_result[0]
                        cursor.execute(f"ALTER TABLE ai_predictions DROP CONSTRAINT {fk_name}")
                        logger.debug(f"Dropped foreign key constraint: {fk_name}")

                    # Make user_id nullable
                    cursor.execute("ALTER TABLE ai_predictions ALTER COLUMN user_id DROP NOT NULL")
                    logger.info("✅ Successfully made ai_predictions.user_id nullable")
                except Exception as e:
                    logger.warning(f"⚠️ Could not migrate ai_predictions.user_id: {e}")

            # Ensure index exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_indexes
                    WHERE tablename = 'ai_predictions'
                    AND indexname = 'idx_ai_predictions_symbol_created'
                )
            """)
            index_exists = cursor.fetchone()[0]
            if not index_exists:
                cursor.execute('''
                    CREATE INDEX idx_ai_predictions_symbol_created ON ai_predictions(symbol, created_at DESC)
                ''')
                logger.info("✅ Created index on ai_predictions")

        # Check and create price_history_cache table
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'price_history_cache'
            )
        """)
        cache_exists = cursor.fetchone()[0]

        if not cache_exists:
            logger.info("📋 Creating missing price_history_cache table...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_history_cache (
                    symbol TEXT PRIMARY KEY,
                    history_data TEXT NOT NULL,
                    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            tables_created.append("price_history_cache")

        # Check and create crypto_prices table
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'crypto_prices'
            )
        """)
        crypto_prices_exists = cursor.fetchone()[0]

        if not crypto_prices_exists:
            logger.info("📋 Creating missing crypto_prices table...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crypto_prices (
                    symbol TEXT PRIMARY KEY,
                    price_usd REAL NOT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_crypto_prices_updated_at ON crypto_prices(updated_at)
            ''')
            tables_created.append("crypto_prices")
        else:
            # Ensure index exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_indexes
                    WHERE tablename = 'crypto_prices'
                    AND indexname = 'idx_crypto_prices_updated_at'
                )
            """)
            index_exists = cursor.fetchone()[0]
            if not index_exists:
                cursor.execute('''
                    CREATE INDEX idx_crypto_prices_updated_at ON crypto_prices(updated_at)
                ''')
                logger.info("✅ Created index on crypto_prices")

        conn.commit()
        conn.close()

        if tables_created:
            logger.info(f"✅ Created missing AI advisor tables: {', '.join(tables_created)}")
        else:
            logger.debug("✅ AI advisor tables already exist")

    except Exception as e:
        logger.error(f"❌ Error ensuring AI advisor tables: {e}", exc_info=True)
        # Don't raise - allow service to continue even if table creation fails


async def populate_initial_prices():
    """Populate crypto_prices table with initial prices from existing portfolio_items or external API"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if crypto_prices table is empty
        cursor.execute("SELECT COUNT(*) FROM crypto_prices")
        count = cursor.fetchone()[0]

        if count > 0:
            logger.debug(f"crypto_prices table already has {count} entries, skipping initial population")
            conn.close()
            return

        # Get all unique symbols from portfolio_items
        sql = _normalize_placeholders(
            "SELECT DISTINCT symbol FROM portfolio_items WHERE symbol IS NOT NULL"
        )
        cursor.execute(sql)
        rows = cursor.fetchall()
        symbols = [row[0] for row in rows if row[0]]
        conn.close()

        if not symbols:
            logger.debug("No symbols found in portfolio_items, skipping initial price population")
            return

        logger.info(f"📊 Populating crypto_prices table with initial prices for {len(symbols)} symbols")

        # Fetch prices from external API
        prices = await multi_exchange_price_service.get_current_prices(symbols)

        if not prices:
            logger.warning("No prices fetched for initial population")
            return

        # Store prices in crypto_prices table
        conn = get_db_connection()
        cursor = conn.cursor()

        for symbol, price_usd in prices.items():
            upsert_sql = _normalize_placeholders(
                """
                INSERT INTO crypto_prices (symbol, price_usd, updated_at, created_at)
                VALUES (%s, %s, NOW(), NOW())
                ON CONFLICT (symbol) DO UPDATE SET
                    price_usd = EXCLUDED.price_usd,
                    updated_at = NOW()
                """
            )
            cursor.execute(upsert_sql, (symbol, price_usd))

        conn.commit()
        conn.close()

        logger.info(f"✅ Populated crypto_prices table with {len(prices)} initial prices")

    except Exception as e:
        logger.error(f"❌ Error populating initial prices: {e}", exc_info=True)
        # Don't raise - allow service to continue even if population fails
