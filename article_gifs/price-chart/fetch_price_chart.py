#!/usr/bin/env python3
"""
Fetch last 30 days of 4H candles + SMA 20/50/200 from gold_analytics DB.
Aggregates gold_prices_1h → 4H via pandas resample.
Output: article_gifs/price-chart/public/data.json

Usage:
    python fetch_price_chart.py
    python fetch_price_chart.py --date 2026-04-11
"""

import json
import math
import os
import sys
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
import psycopg2
import psycopg2.extras
import ta
from dotenv import load_dotenv

# .env is two directories up (project root)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def clean(v):
    try:
        if v is None or math.isnan(v): return None
        return round(float(v), 1)
    except Exception:
        return None


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

    # Fetch ~120 days to ensure SMA200 on 4H bars has full warm-up (200×4h = 800h ≈ 34 days).
    # 120 days gives a comfortable buffer without loading the full DB history.
    if target_date:
        cur.execute("""
            SELECT timestamp, open, high, low, close
            FROM gold_prices.gold_prices_1h
            WHERE timestamp >= (%s::timestamptz - INTERVAL '120 days')
              AND timestamp <= %s::timestamptz
            ORDER BY timestamp ASC
        """, (target_date + " 23:59:59", target_date + " 23:59:59"))
    else:
        cur.execute("""
            SELECT timestamp, open, high, low, close
            FROM gold_prices.gold_prices_1h
            WHERE timestamp >= NOW() - INTERVAL '120 days'
            ORDER BY timestamp ASC
        """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # SMA200 on 4H bars needs 200×4 = 800 hourly rows minimum
    if len(rows) < 800:
        print(f"Not enough data: {len(rows)} hourly rows (need ≥800 for SMA200).")
        sys.exit(1)

    df = pd.DataFrame([dict(r) for r in rows])
    df = df.astype({"open": float, "high": float, "low": float, "close": float})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()

    # Aggregate 1H → 4H (anchored at midnight UTC)
    df4 = df.resample("4h", offset="0h").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
    ).dropna()

    df4["sma20"]  = ta.trend.sma_indicator(df4["close"], window=20).round(1)
    df4["sma50"]  = ta.trend.sma_indicator(df4["close"], window=50).round(1)
    df4["sma200"] = ta.trend.sma_indicator(df4["close"], window=200).round(1)

    # Last 30 days = 30×6 = 180 four-hour bars
    last30 = df4.tail(30 * 6).copy()
    latest = last30.iloc[-1]

    candles = []
    for ts, row in last30.iterrows():
        candles.append({
            "date":   ts.strftime("%Y-%m-%dT%H:%M"),
            "open":   round(float(row["open"]),  1),
            "high":   round(float(row["high"]),  1),
            "low":    round(float(row["low"]),   1),
            "close":  round(float(row["close"]), 1),
            "sma20":  clean(row["sma20"]),
            "sma50":  clean(row["sma50"]),
            "sma200": clean(row["sma200"]),
        })

    output = {
        "date":          last30.index[-1].strftime("%Y-%m-%d"),
        "date_from":     last30.index[0].strftime("%Y-%m-%d"),
        "current_price": round(float(latest["close"]), 1),
        "candles":       candles,
        "sma20":         clean(latest["sma20"]),
        "sma50":         clean(latest["sma50"]),
        "sma200":        clean(latest["sma200"]),
    }

    output_path = os.path.join(os.path.dirname(__file__), "public", "data.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, cls=DecimalEncoder)

    print(f"OK  {output['date']}  ${float(latest['close']):,.1f}")
    print(f"    SMA20: {output['sma20']}  SMA50: {output['sma50']}  SMA200: {output['sma200']}")
    print(f"    Range: ${last30['low'].min():.0f} – ${last30['high'].max():.0f}")


if __name__ == "__main__":
    main()
