-- ============================================================
-- Fed Rates Schema
-- ============================================================

CREATE SCHEMA IF NOT EXISTS fed_rates;

-- FRED series metadata
CREATE TABLE IF NOT EXISTS fed_rates.series (
    id          TEXT PRIMARY KEY,           -- FRED series ID e.g. 'FEDFUNDS'
    title       TEXT NOT NULL,
    frequency   TEXT NOT NULL,              -- 'Daily', 'Monthly'
    units       TEXT NOT NULL,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Series observations
CREATE TABLE IF NOT EXISTS fed_rates.observations (
    id          SERIAL PRIMARY KEY,
    series_id   TEXT NOT NULL REFERENCES fed_rates.series(id),
    date        DATE NOT NULL,
    value       NUMERIC NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(series_id, date)
);
