-- ============================================================
-- Gold Analytics - Database Schema (PostgreSQL)
-- ============================================================

-- XAU/USD price candles (OHLCV)
CREATE TABLE IF NOT EXISTS gold_prices (
    id          SERIAL PRIMARY KEY,
    timestamp   TIMESTAMP NOT NULL,
    timeframe   TEXT NOT NULL,         -- '1d', '1w', '1h'
    open        NUMERIC NOT NULL,
    high        NUMERIC NOT NULL,
    low         NUMERIC NOT NULL,
    close       NUMERIC NOT NULL,
    volume      NUMERIC,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(timestamp, timeframe)
);

-- Correlated instruments prices (DXY, US10Y, Oil, Silver, SP500)
CREATE TABLE IF NOT EXISTS correlated_assets (
    id          SERIAL PRIMARY KEY,
    timestamp   TIMESTAMP NOT NULL,
    symbol      TEXT NOT NULL,         -- 'DXY', 'US10Y', 'WTI', 'XAGUSD', 'SPX'
    close       NUMERIC NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(timestamp, symbol)
);

-- News articles related to gold / macro
CREATE TABLE IF NOT EXISTS news (
    id           SERIAL PRIMARY KEY,
    published_at TIMESTAMP NOT NULL,
    source       TEXT,
    title        TEXT NOT NULL,
    summary      TEXT,
    url          TEXT,
    sentiment    TEXT,                 -- 'bullish', 'bearish', 'neutral'
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Upcoming economic calendar events
CREATE TABLE IF NOT EXISTS economic_events (
    id          SERIAL PRIMARY KEY,
    event_date  TIMESTAMP NOT NULL,
    country     TEXT NOT NULL,         -- 'US', 'EU', 'CN'
    event_name  TEXT NOT NULL,         -- 'CPI', 'NFP', 'FOMC'
    impact      TEXT NOT NULL,         -- 'high', 'medium', 'low'
    forecast    TEXT,
    previous    TEXT,
    actual      TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_date, event_name, country)
);

-- Generated articles
CREATE TABLE IF NOT EXISTS articles (
    id              SERIAL PRIMARY KEY,
    generated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    prediction      TEXT,              -- 'bullish', 'bearish', 'neutral'
    target_price    NUMERIC,
    week_start      DATE,
    week_end        DATE,
    published       BOOLEAN DEFAULT FALSE
);
