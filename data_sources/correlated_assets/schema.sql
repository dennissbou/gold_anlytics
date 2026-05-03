-- ============================================================
-- Correlated Assets Schema
-- ============================================================

CREATE SCHEMA IF NOT EXISTS correlated_assets;

-- Daily OHLCV for all correlated instruments
CREATE TABLE IF NOT EXISTS correlated_assets.prices_1d (
    id          SERIAL PRIMARY KEY,
    timestamp   TIMESTAMP NOT NULL,
    symbol      TEXT NOT NULL,      -- 'DXY', 'US10Y', 'WTI', 'SILVER', 'SPX', 'VIX'
    open        NUMERIC,
    high        NUMERIC,
    low         NUMERIC,
    close       NUMERIC NOT NULL,
    volume      NUMERIC,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(timestamp, symbol)
);
