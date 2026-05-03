-- ============================================================
-- ETF Flows Schema
-- ============================================================

CREATE SCHEMA IF NOT EXISTS etf_flows;

-- Monthly global gold ETF holdings in tonnes by region (WGC data)
CREATE TABLE IF NOT EXISTS etf_flows.holdings_monthly (
    id              SERIAL PRIMARY KEY,
    month           DATE NOT NULL UNIQUE,   -- first day of month
    north_america   NUMERIC,                -- tonnes
    europe          NUMERIC,                -- tonnes
    asia            NUMERIC,                -- tonnes
    other           NUMERIC,                -- tonnes
    total           NUMERIC,                -- derived: sum of all regions
    gold_price_usd  NUMERIC,                -- gold price at month end (WGC reference)
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Monthly global gold ETF flows in USD by region (WGC data)
CREATE TABLE IF NOT EXISTS etf_flows.flows_monthly (
    id              SERIAL PRIMARY KEY,
    month           DATE NOT NULL UNIQUE,
    north_america   NUMERIC,                -- USD net flow
    europe          NUMERIC,
    asia            NUMERIC,
    other           NUMERIC,
    total           NUMERIC,                -- derived: sum of all regions
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
