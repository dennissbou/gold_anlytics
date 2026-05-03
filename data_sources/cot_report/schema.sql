-- ============================================================
-- COT Report Schema
-- ============================================================

CREATE SCHEMA IF NOT EXISTS cot_report;

-- Weekly CFTC Commitments of Traders — Gold Futures (COMEX)
CREATE TABLE IF NOT EXISTS cot_report.gold_futures (
    id                      SERIAL PRIMARY KEY,
    report_date             DATE NOT NULL UNIQUE,
    open_interest           INTEGER NOT NULL,
    noncomm_long            INTEGER NOT NULL,   -- speculative longs
    noncomm_short           INTEGER NOT NULL,   -- speculative shorts
    noncomm_net             INTEGER NOT NULL,   -- derived: long - short
    comm_long               INTEGER NOT NULL,   -- commercial (hedger) longs
    comm_short              INTEGER NOT NULL,   -- commercial (hedger) shorts
    comm_net                INTEGER NOT NULL,   -- derived: long - short
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
