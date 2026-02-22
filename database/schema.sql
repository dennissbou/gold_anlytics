-- ============================================================
-- Gold Analytics - Database Schema
-- ============================================================

-- XAU/USD price candles (OHLCV)
CREATE TABLE IF NOT EXISTS gold_prices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   DATETIME NOT NULL,
    timeframe   TEXT NOT NULL,         -- '1d', '1w', '1h'
    open        REAL NOT NULL,
    high        REAL NOT NULL,
    low         REAL NOT NULL,
    close       REAL NOT NULL,
    volume      REAL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(timestamp, timeframe)
);

-- Correlated instruments prices (DXY, US10Y, Oil, Silver, SP500)
CREATE TABLE IF NOT EXISTS correlated_assets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   DATETIME NOT NULL,
    symbol      TEXT NOT NULL,         -- 'DXY', 'US10Y', 'WTI', 'XAGUSD', 'SPX'
    close       REAL NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(timestamp, symbol)
);

-- News articles related to gold / macro
CREATE TABLE IF NOT EXISTS news (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    published_at DATETIME NOT NULL,
    source      TEXT,
    title       TEXT NOT NULL,
    summary     TEXT,
    url         TEXT,
    sentiment   TEXT,                  -- 'bullish', 'bearish', 'neutral'
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Upcoming economic calendar events
CREATE TABLE IF NOT EXISTS economic_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date  DATETIME NOT NULL,
    country     TEXT NOT NULL,         -- 'US', 'EU', 'CN'
    event_name  TEXT NOT NULL,         -- 'CPI', 'NFP', 'FOMC'
    impact      TEXT NOT NULL,         -- 'high', 'medium', 'low'
    forecast    TEXT,
    previous    TEXT,
    actual      TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_date, event_name, country)
);

-- Generated articles
CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    prediction      TEXT,              -- 'bullish', 'bearish', 'neutral'
    target_price    REAL,
    week_start      DATE,
    week_end        DATE,
    published       INTEGER DEFAULT 0  -- 0=draft, 1=published
);
