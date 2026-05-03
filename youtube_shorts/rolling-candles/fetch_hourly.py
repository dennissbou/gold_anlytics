#!/usr/bin/env python3
"""
Fetch 24h hourly candle data from gold_analytics and export to public/data.json
Run this before rendering the video.

Usage:
    python fetch_hourly.py                    # Last 24 hours
    python fetch_hourly.py --date 2026-03-24  # Specific date
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
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
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "gold_analytics"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def fetch_day(d: str) -> list[dict]:
        cur.execute("""
            SELECT
                TO_CHAR(timestamp, 'HH24:MI') AS hour,
                open, high, low, close
            FROM gold_prices.gold_prices_1h
            WHERE DATE(timestamp) = %s
            ORDER BY timestamp
        """, (d,))
        return [
            {
                "hour": r["hour"],
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
            }
            for r in cur.fetchall()
        ]

    try:
        # Always resolve to the latest date that actually has data in DB
        cur.execute("SELECT MAX(DATE(timestamp)) AS max_date FROM gold_prices.gold_prices_1h")
        latest_date = cur.fetchone()["max_date"].isoformat()

        if target_date:
            current_date = target_date
            candles = fetch_day(current_date)
            if not candles:
                print(f"⚠ No hourly data found for {current_date}, falling back to latest: {latest_date}")
                current_date = latest_date
        else:
            current_date = latest_date

        prev_date = (datetime.strptime(current_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

        candles = fetch_day(current_date)
        prev_candles = fetch_day(prev_date)

        if not candles:
            print(f"⚠ No hourly data found for {current_date}.")
            candles = []

        if not prev_candles:
            print(f"⚠ No previous day data found for {prev_date}.")

    except psycopg2.errors.UndefinedTable:
        conn.rollback()
        print("⚠ Table 'gold_prices.gold_prices_1h' does not exist.")
        print("  Run: python database/init_db.py to initialise all schemas.")
        candles = []
        prev_candles = []

    cur.close()
    conn.close()

    if not candles:
        print("No data to export. Exiting.")
        sys.exit(1)

    open_price = candles[0]["open"]
    close_price = candles[-1]["close"]
    day_high = max(c["high"] for c in candles)
    day_low = min(c["low"] for c in candles)
    change_pct = round((close_price - open_price) / open_price * 100, 2)

    output = {
        "candles": candles,
        "prev_candles": prev_candles,
        "date": current_date,
        "open_price": open_price,
        "close_price": close_price,
        "high": day_high,
        "low": day_low,
        "change_pct": change_pct,
    }
    output_path = os.path.join(os.path.dirname(__file__), "public", "data.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, cls=DecimalEncoder)

    print(f"OK Exported {len(candles)} candles + {len(prev_candles)} prev-day candles to {output_path}")
    print(f"   Date:  {current_date} ({candles[0]['hour']} to {candles[-1]['hour']})")
    print(f"   Price: ${candles[0]['open']:,.0f} to ${candles[-1]['close']:,.0f} ({change_pct:+.2f}%)")


if __name__ == "__main__":
    main()
