-- ============================================================
-- News Schema
-- ============================================================

CREATE SCHEMA IF NOT EXISTS news;

-- Gold-related news articles from Yahoo Finance (via yfinance)
CREATE TABLE IF NOT EXISTS news.articles (
    id          TEXT PRIMARY KEY,           -- Yahoo article UUID (dedup key)
    published_at TIMESTAMP NOT NULL,
    title       TEXT NOT NULL,
    summary     TEXT,
    url         TEXT,
    source      TEXT,                       -- provider display name
    ticker      TEXT,                       -- which ticker it was fetched from
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
