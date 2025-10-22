-- Enhanced Database Schema for Crypto AI Agent v2
-- PostgreSQL schema for Next.js + FastAPI migration

-- Portfolio table (enhanced)
CREATE TABLE portfolio (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    amount DECIMAL(20,8) NOT NULL,
    price_buy DECIMAL(20,8) NOT NULL,
    purchase_date TIMESTAMP,
    base_currency VARCHAR(3) NOT NULL,
    purchase_price_eur DECIMAL(20,8),
    purchase_price_czk DECIMAL(20,8),
    source VARCHAR(50),
    commission DECIMAL(20,8) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Currency rates table
CREATE TABLE currency_rates (
    id SERIAL PRIMARY KEY,
    from_currency VARCHAR(3) NOT NULL,
    to_currency VARCHAR(3) NOT NULL,
    rate DECIMAL(20,8) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Price alerts table
CREATE TABLE price_alerts (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    alert_type VARCHAR(10) NOT NULL,
    threshold_price DECIMAL(20,8) NOT NULL,
    message TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alert history table
CREATE TABLE alert_history (
    id SERIAL PRIMARY KEY,
    alert_id INTEGER REFERENCES price_alerts(id),
    symbol VARCHAR(10) NOT NULL,
    triggered_price DECIMAL(20,8) NOT NULL,
    threshold_price DECIMAL(20,8) NOT NULL,
    alert_type VARCHAR(10) NOT NULL,
    message TEXT,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tracked symbols table
CREATE TABLE tracked_symbols (
    symbol VARCHAR(10) PRIMARY KEY,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crypto symbols table
CREATE TABLE crypto_symbols (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(100),
    description TEXT,
    is_tradable BOOLEAN DEFAULT TRUE,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Candles table (price history)
CREATE TABLE candles (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Comprehensive indexes for performance optimization
-- Portfolio indexes
CREATE INDEX idx_portfolio_symbol ON portfolio(symbol);
CREATE INDEX idx_portfolio_base_currency ON portfolio(base_currency);
CREATE INDEX idx_portfolio_created_at ON portfolio(created_at);
CREATE INDEX idx_portfolio_symbol_currency ON portfolio(symbol, base_currency);

-- Currency rates indexes
CREATE INDEX idx_currency_rates_timestamp ON currency_rates(timestamp);
CREATE INDEX idx_currency_rates_currencies ON currency_rates(from_currency, to_currency);
CREATE INDEX idx_currency_rates_latest ON currency_rates(from_currency, to_currency, timestamp DESC);

-- Price alerts indexes
CREATE INDEX idx_price_alerts_symbol ON price_alerts(symbol);
CREATE INDEX idx_price_alerts_active ON price_alerts(is_active);
CREATE INDEX idx_price_alerts_symbol_active ON price_alerts(symbol, is_active);
CREATE INDEX idx_price_alerts_created_at ON price_alerts(created_at);

-- Alert history indexes
CREATE INDEX idx_alert_history_triggered_at ON alert_history(triggered_at);
CREATE INDEX idx_alert_history_alert_id ON alert_history(alert_id);
CREATE INDEX idx_alert_history_symbol ON alert_history(symbol);
CREATE INDEX idx_alert_history_symbol_triggered ON alert_history(symbol, triggered_at DESC);

-- Candles indexes
CREATE INDEX idx_candles_symbol_timestamp ON candles(symbol, timestamp);
CREATE INDEX idx_candles_timestamp ON candles(timestamp);
CREATE INDEX idx_candles_symbol_latest ON candles(symbol, timestamp DESC);

-- Tracked symbols indexes
CREATE INDEX idx_tracked_symbols_active ON tracked_symbols(is_active);
CREATE INDEX idx_tracked_symbols_created_at ON tracked_symbols(created_at);

-- Crypto symbols indexes
CREATE INDEX idx_crypto_symbols_tradable ON crypto_symbols(is_tradable);
CREATE INDEX idx_crypto_symbols_last_updated ON crypto_symbols(last_updated);
CREATE INDEX idx_crypto_symbols_symbol_tradable ON crypto_symbols(symbol, is_tradable);

-- Composite indexes for common queries
CREATE INDEX idx_portfolio_summary ON portfolio(symbol, base_currency, amount, price_buy);
CREATE INDEX idx_alerts_active_symbols ON price_alerts(symbol) WHERE is_active = true;
CREATE INDEX idx_currency_rates_recent ON currency_rates(from_currency, to_currency, timestamp DESC) WHERE timestamp > NOW() - INTERVAL '1 hour';

-- Insert initial tracked symbols
INSERT INTO tracked_symbols (symbol, is_active) VALUES 
('BTC', true)
ON CONFLICT (symbol) DO NOTHING;
