#!/usr/bin/env python3
"""
Fetch technical indicators from gold_analytics and export to public/data.json.

Usage:
    python fetch_technicals.py
    python fetch_technicals.py --date 2026-03-28
"""

import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
import psycopg2
import psycopg2.extras
import ta
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
        if target_date:
            cur.execute("""
                SELECT timestamp, open, high, low, close
                FROM gold_prices.gold_prices_1d
                WHERE timestamp::date <= %s
                ORDER BY timestamp ASC
            """, (target_date,))
        else:
            cur.execute("""
                SELECT timestamp, open, high, low, close
                FROM gold_prices.gold_prices_1d
                ORDER BY timestamp ASC
            """)
        rows = cur.fetchall()
    except psycopg2.errors.UndefinedTable:
        conn.rollback()
        print("Table 'gold_prices.gold_prices_1d' does not exist.")
        print("Run: python database/init_db.py to initialise all schemas.")
        sys.exit(1)

    cur.close()
    conn.close()

    if len(rows) < 26:
        print(f"Not enough data: {len(rows)} candles (need at least 26).")
        sys.exit(1)

    # Build DataFrame
    df = pd.DataFrame([dict(r) for r in rows])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")
    df = df.astype(float)

    # ── Technical indicators ──────────────────────────────────────────────────
    df["sma20"]  = ta.trend.sma_indicator(df["close"], window=20)
    df["sma50"]  = ta.trend.sma_indicator(df["close"], window=50)
    df["sma200"] = ta.trend.sma_indicator(df["close"], window=200)

    df["rsi"] = ta.momentum.rsi(df["close"], window=14)

    macd_obj      = ta.trend.MACD(df["close"])
    df["macd"]        = macd_obj.macd()
    df["macd_signal"] = macd_obj.macd_signal()
    df["macd_hist"]   = macd_obj.macd_diff()

    bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_mid"]   = bb.bollinger_mavg()

    df["atr"] = ta.volatility.average_true_range(
        df["high"], df["low"], df["close"], window=14
    )

    latest = df.iloc[-1]
    price  = float(latest["close"])

    used_date = df.index[-1]
    used_date_str = used_date.date().isoformat() if hasattr(used_date, "date") else str(used_date)[:10]

    # Override current_price with last hourly candle (consistent with rolling-candles frame)
    conn2 = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "gold_analytics"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    cur2 = conn2.cursor()
    if target_date:
        cur2.execute("""
            SELECT close FROM gold_prices.gold_prices_1h
            WHERE timestamp::date <= %s
            ORDER BY timestamp DESC LIMIT 1
        """, (target_date,))
    else:
        cur2.execute("""
            SELECT close FROM gold_prices.gold_prices_1h
            ORDER BY timestamp DESC LIMIT 1
        """)
    h_row = cur2.fetchone()
    if h_row:
        price = float(h_row[0])
    cur2.close()
    conn2.close()

    # Trend
    sma20  = round(float(latest["sma20"]),  1)
    sma50  = round(float(latest["sma50"]),  1)
    sma200 = round(float(latest["sma200"]), 1)

    diff_pct = (price - sma20) / sma20 * 100
    if diff_pct > 0.5:
        trend = "uptrend"
    elif diff_pct < -0.5:
        trend = "downtrend"
    else:
        trend = "sideways"

    # Bollinger Band position (0-100 %)
    bb_upper = round(float(latest["bb_upper"]), 1)
    bb_lower = round(float(latest["bb_lower"]), 1)
    bb_mid   = round(float(latest["bb_mid"]),   1)
    bb_width = bb_upper - bb_lower
    bb_pct   = round((price - bb_lower) / bb_width * 100, 1) if bb_width > 0 else 50.0

    # ATR
    atr     = round(float(latest["atr"]), 1)
    atr_pct = round(atr / price * 100, 2)

    # MACD histogram series: last 20 bars (for mini bar chart animation)
    hist_series = []
    for ts, row in df.iloc[-20:].dropna(subset=["macd_hist"]).iterrows():
        ts_str = ts.date().isoformat() if hasattr(ts, "date") else str(ts)[:10]
        hist_series.append({
            "date":      ts_str,
            "macd_hist": round(float(row["macd_hist"]), 4),
        })

    output = {
        "date":          used_date_str,
        "current_price": round(price, 1),
        "trend":         trend,
        "rsi":           round(float(latest["rsi"]),         1),
        "macd":          round(float(latest["macd"]),         3),
        "macd_signal":   round(float(latest["macd_signal"]),  3),
        "macd_hist":     round(float(latest["macd_hist"]),    3),
        "hist_series":   hist_series,
        "sma20":         sma20,
        "sma50":         sma50,
        "sma200":        sma200,
        "bb_upper":      bb_upper,
        "bb_mid":        bb_mid,
        "bb_lower":      bb_lower,
        "bb_pct":        bb_pct,
        "atr":           atr,
        "atr_pct":       atr_pct,
    }

    output_path = os.path.join(os.path.dirname(__file__), "public", "data.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, cls=DecimalEncoder)

    rsi_val   = output["rsi"]
    rsi_label = "overbought" if rsi_val > 70 else ("oversold" if rsi_val < 30 else "neutral")
    sign      = lambda v: f"+{v}" if v >= 0 else str(v)

    print(f"OK  {used_date_str}  |  ${price:,.1f}  |  {trend}")
    print(f"    RSI: {rsi_val} ({rsi_label})  |  MACD hist: {sign(output['macd_hist'])}")
    print(f"    BB:  ${bb_lower:,.1f} / ${bb_mid:,.1f} / ${bb_upper:,.1f}  ({bb_pct:.1f}% of range)")
    print(f"    ATR: ${atr:.1f} ({atr_pct:.2f}%)  |  SMA20 ${sma20:,.1f}  SMA50 ${sma50:,.1f}  SMA200 ${sma200:,.1f}")


if __name__ == "__main__":
    main()
