-- ============================================================
-- Central Bank Schema
-- ============================================================

CREATE SCHEMA IF NOT EXISTS central_bank;

-- Monthly gold reserves by country (in tonnes)
CREATE TABLE IF NOT EXISTS central_bank.gold_reserves (
    id          SERIAL PRIMARY KEY,
    month       DATE NOT NULL,              -- first day of month: 2024-01-01
    country     TEXT NOT NULL,              -- 'US', 'CN', 'DE', 'RU', 'IN', etc.
    tonnes      NUMERIC NOT NULL,           -- official gold holdings in metric tonnes
    source      TEXT DEFAULT 'IMF_IFS',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(month, country)
);
