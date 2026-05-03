-- ============================================================
-- Economic Calendar Schema
-- ============================================================

CREATE SCHEMA IF NOT EXISTS economic_calendar;

-- Economic events: past releases and upcoming scheduled dates
CREATE TABLE IF NOT EXISTS economic_calendar.events (
    id          SERIAL PRIMARY KEY,
    event_date  DATE NOT NULL,
    event_name  TEXT NOT NULL,              -- 'CPI', 'NFP', 'FOMC', 'GDP', 'PPI', 'PCE'
    country     TEXT NOT NULL DEFAULT 'US',
    impact      TEXT NOT NULL DEFAULT 'high',
    actual      NUMERIC,                    -- NULL if not yet released
    forecast    NUMERIC,                    -- analyst consensus (if available)
    previous    NUMERIC,                    -- prior release value
    source      TEXT,                       -- 'FRED'
    fred_series TEXT,                       -- FRED series ID for actual value
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_date, event_name, country)
);
