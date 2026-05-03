-- ============================================================
-- Locale Data Schema
-- Per-country FX rates and macro indicators used by the locale article generator.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS locale_data;

-- Daily FX snapshot: 1 USD = X local currency + 30-day trend
CREATE TABLE IF NOT EXISTS locale_data.fx_rates (
    id               SERIAL PRIMARY KEY,
    fetched_date     DATE           NOT NULL,
    locale           TEXT           NOT NULL,
    currency         TEXT           NOT NULL,
    rate_usd         NUMERIC(20, 6) NOT NULL,
    change_30d_pct   NUMERIC(8, 4),
    fx_trend         TEXT,                      -- 'weakening' | 'strengthening' | 'stable'
    gold_price_usd   NUMERIC(12, 4),
    gold_price_local NUMERIC(20, 4),
    created_at       TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (fetched_date, locale)
);

-- World Bank macro indicators (annual data, one row per locale)
CREATE TABLE IF NOT EXISTS locale_data.macro (
    locale               TEXT PRIMARY KEY,
    iso2                 TEXT        NOT NULL,
    inflation_annual_pct NUMERIC(8, 4),
    inflation_year       INTEGER,
    gdp_growth_pct       NUMERIC(8, 4),
    gdp_year             INTEGER,
    updated_at           TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- Central bank policy rates (one row per locale, upserted on change)
CREATE TABLE IF NOT EXISTS locale_data.central_bank_rates (
    locale          TEXT PRIMARY KEY,
    iso2            TEXT        NOT NULL,
    bank_name       TEXT        NOT NULL,
    source          TEXT,                       -- 'fred' | 'bcb' | 'banxico' | 'bcrp' | null
    policy_rate     NUMERIC(8, 4),
    previous_rate   NUMERIC(8, 4),
    rate_change     NUMERIC(8, 4),
    rate_trend      TEXT,                       -- 'hiking' | 'cutting' | 'holding'
    rate_date       DATE,
    updated_at      TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_locale_data_fx_rates_locale_date
    ON locale_data.fx_rates (locale, fetched_date DESC);
