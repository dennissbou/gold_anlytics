#!/usr/bin/env python3
"""
Fetch daily gold stats from gold_analytics and export to public/data.json.

Usage:
    python fetch_stats.py                    # Latest available date in DB
    python fetch_stats.py --date 2026-03-18  # Specific date
"""

import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def main():
    target_date = None
    if len(sys.argv) > 2 and sys.argv[1] == "--date":
        target_date = sys.argv[2]

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "gold_analytics"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        # Fetch last 65 daily candles (need 60 for support/resistance, 22 for month change)
        if target_date:
            cur.execute("""
                SELECT timestamp, open, high, low, close
                FROM gold_prices.gold_prices_1d
                WHERE timestamp::date <= %s
                ORDER BY timestamp DESC
                LIMIT 65
            """, (target_date,))
        else:
            cur.execute("""
                SELECT timestamp, open, high, low, close
                FROM gold_prices.gold_prices_1d
                ORDER BY timestamp DESC
                LIMIT 65
            """)

        rows = list(reversed([
            {k: float(v) if isinstance(v, Decimal) else v for k, v in dict(r).items()}
            for r in cur.fetchall()
        ]))

    except psycopg2.errors.UndefinedTable:
        conn.rollback()
        print("Table 'gold_prices.gold_prices_1d' does not exist.")
        print("Run: python database/init_db.py to initialise all schemas.")
        sys.exit(1)

    # Fetch last hourly close for target date (matches what rolling-candles shows)
    hourly_close = None
    try:
        if target_date:
            cur.execute("""
                SELECT close FROM gold_prices.gold_prices_1h
                WHERE DATE(timestamp) = %s
                ORDER BY timestamp DESC
                LIMIT 1
            """, (target_date,))
        else:
            cur.execute("""
                SELECT close FROM gold_prices.gold_prices_1h
                WHERE DATE(timestamp) = (
                    SELECT DATE(timestamp) FROM gold_prices.gold_prices_1d
                    ORDER BY timestamp DESC LIMIT 1
                )
                ORDER BY timestamp DESC
                LIMIT 1
            """)
        row = cur.fetchone()
        if row:
            hourly_close = float(row["close"])
    except Exception:
        conn.rollback()

    cur.close()
    conn.close()

    if len(rows) < 22:
        print(f"Not enough data: only {len(rows)} daily candles available (need at least 22).")
        sys.exit(1)

    # ── Stats ─────────────────────────────────────────────────────────────────

    # Use hourly close if available — matches the price the candle animation ends at
    current_price = hourly_close if hourly_close is not None else float(rows[-1]["close"])
    used_date = rows[-1]["timestamp"]
    if hasattr(used_date, "date"):
        used_date = used_date.date().isoformat()
    else:
        used_date = str(used_date)[:10]

    # Week change: 7 trading days back
    week_ref = rows[-7]["close"] if len(rows) >= 7 else rows[0]["close"]
    week_pct = round((current_price - float(week_ref)) / float(week_ref) * 100, 2)

    # Week series: cumulative % change from day -7 for each of the 7 days
    week_rows = rows[-7:] if len(rows) >= 7 else rows
    base = float(week_rows[0]["close"])
    week_series = []
    for i, r in enumerate(week_rows):
        ts = r["timestamp"]
        label = ts.date().strftime("%b %d") if hasattr(ts, "date") else str(ts)[:10]
        # Last entry uses current_price (hourly close) so it matches the candle
        price = round(current_price if i == len(week_rows) - 1 else float(r["close"]), 1)
        pct = round((price - base) / base * 100, 2)
        week_series.append({"label": label, "price": price, "pct": pct})

    # Month change: 22 trading days back (approx 1 month)
    month_rows = rows[-22:] if len(rows) >= 22 else rows
    month_ref = float(month_rows[0]["close"])
    month_pct = round((current_price - month_ref) / month_ref * 100, 2)
    month_series = []
    for i, r in enumerate(month_rows):
        ts = r["timestamp"]
        label = ts.date().strftime("%b %d") if hasattr(ts, "date") else str(ts)[:10]
        # Last entry uses current_price (hourly close) so it matches the candle
        price = round(current_price if i == len(month_rows) - 1 else float(r["close"]), 1)
        pct = round((price - month_ref) / month_ref * 100, 2)
        month_series.append({"label": label, "price": price, "pct": pct})

    # Support: lowest low of last 60 days
    recent = rows[-60:] if len(rows) >= 60 else rows
    support = round(float(min(r["low"] for r in recent)), 1)

    # Resistance: highest high of last 60 days
    resistance = round(float(max(r["high"] for r in recent)), 1)

    # ── Output ────────────────────────────────────────────────────────────────

    output = {
        "date": used_date,
        "current_price": round(current_price, 1),
        "week_pct": week_pct,
        "week_series": week_series,
        "month_pct": month_pct,
        "month_series": month_series,
        "support": support,
        "resistance": resistance,
    }

    output_path = os.path.join(os.path.dirname(__file__), "public", "data.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, cls=DecimalEncoder)

    # Also write to rolling-candles so both blocks use identical numbers
    candles_stat_path = os.path.join(os.path.dirname(__file__), "..", "rolling-candles", "public", "stat_data.json")
    with open(candles_stat_path, "w") as f:
        json.dump(output, f, indent=2, cls=DecimalEncoder)

    sign = lambda v: f"+{v}" if v >= 0 else str(v)
    print(f"OK Fetched stats for {used_date}")
    print(f"   Price: ${current_price:,.1f}  |  Week: {sign(week_pct)}%  |  Month: {sign(month_pct)}%")
    print(f"   Support: ${support:,.1f}  |  Resistance: ${resistance:,.1f}")


if __name__ == "__main__":
    main()
