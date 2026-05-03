-- ============================================================
-- Gold Prices Schema
-- ============================================================

CREATE SCHEMA IF NOT EXISTS gold_prices;

-- XAU/USD daily candles (OHLCV)
CREATE TABLE IF NOT EXISTS gold_prices.gold_prices_1d (
    id          SERIAL PRIMARY KEY,
    timestamp   TIMESTAMP NOT NULL UNIQUE,
    open        NUMERIC NOT NULL,
    high        NUMERIC NOT NULL,
    low         NUMERIC NOT NULL,
    close       NUMERIC NOT NULL,
    volume      NUMERIC,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- XAU/USD 1-hour candles (OHLCV)
CREATE TABLE IF NOT EXISTS gold_prices.gold_prices_1h (
    id          SERIAL PRIMARY KEY,
    timestamp   TIMESTAMP NOT NULL UNIQUE,
    open        NUMERIC NOT NULL,
    high        NUMERIC NOT NULL,
    low         NUMERIC NOT NULL,
    close       NUMERIC NOT NULL,
    volume      NUMERIC,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
