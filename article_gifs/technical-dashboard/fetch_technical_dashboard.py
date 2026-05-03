#!/usr/bin/env python3
"""
Fetch technical indicators from gold_analytics and export to public/data.json.
(Article GIF variant — output path differs from youtube_shorts version.)

Usage:
    python fetch_technical_dashboard.py
    python fetch_technical_dashboard.py --date 2026-04-11
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

# .env is two directories up from this script (project root)
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
    cur.close()
    conn.close()

    if len(rows) < 26:
        print(f"Not enough data: {len(rows)} candles (need at least 26).")
        sys.exit(1)

    df = pd.DataFrame([dict(r) for r in rows])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").astype(float)

    df["sma20"]  = ta.trend.sma_indicator(df["close"], window=20)
    df["sma50"]  = ta.trend.sma_indicator(df["close"], window=50)
    df["sma200"] = ta.trend.sma_indicator(df["close"], window=200)
    df["rsi"]    = ta.momentum.rsi(df["close"], window=14)

    macd_obj          = ta.trend.MACD(df["close"])
    df["macd"]        = macd_obj.macd()
    df["macd_signal"] = macd_obj.macd_signal()
    df["macd_hist"]   = macd_obj.macd_diff()

    bb              = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
    df["bb_upper"]  = bb.bollinger_hband()
    df["bb_lower"]  = bb.bollinger_lband()
    df["bb_mid"]    = bb.bollinger_mavg()
    df["atr"]       = ta.volatility.average_true_range(
        df["high"], df["low"], df["close"], window=14
    )

    latest    = df.iloc[-1]
    used_date = df.index[-1].date().isoformat()

    # Use latest hourly close as current_price for consistency with other GIF blocks
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
            WHERE timestamp <= %s::timestamptz
            ORDER BY timestamp DESC LIMIT 1
        """, (target_date + " 23:59:59",))
    else:
        cur2.execute("""
            SELECT close FROM gold_prices.gold_prices_1h
            ORDER BY timestamp DESC LIMIT 1
        """)
    row1h = cur2.fetchone()
    cur2.close()
    conn2.close()
    price = float(row1h[0]) if row1h else float(latest["close"])

    sma20  = round(float(latest["sma20"]),  1)
    sma50  = round(float(latest["sma50"]),  1)
    sma200 = round(float(latest["sma200"]), 1)

    bb_upper = round(float(latest["bb_upper"]), 1)
    bb_lower = round(float(latest["bb_lower"]), 1)
    bb_mid   = round(float(latest["bb_mid"]),   1)
    bb_width = bb_upper - bb_lower
    bb_pct   = round((price - bb_lower) / bb_width * 100, 1) if bb_width > 0 else 50.0

    atr     = round(float(latest["atr"]), 1)
    atr_pct = round(atr / price * 100, 2)

    hist_series = []
    for ts, row in df.iloc[-7:].dropna(subset=["macd_hist"]).iterrows():
        hist_series.append({
            "date":      ts.date().isoformat(),
            "macd_hist": round(float(row["macd_hist"]), 4),
        })

    _months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    def _fmt(d: str) -> str:
        _, m, day = d.split("-")
        return f"{int(day):02d} {_months[int(m)-1]}"
    period = (
        f"{_fmt(hist_series[0]['date'])} – {_fmt(hist_series[-1]['date'])}"
        if hist_series else used_date
    )

    output = {
        "date":          used_date,
        "period":        period,
        "current_price": round(price, 1),
        "rsi":           round(float(latest["rsi"]),        1),
        "macd":          round(float(latest["macd"]),        3),
        "macd_signal":   round(float(latest["macd_signal"]), 3),
        "macd_hist":     round(float(latest["macd_hist"]),   3),
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

    rsi_label = "overbought" if output["rsi"] > 70 else ("oversold" if output["rsi"] < 30 else "neutral")
    print(f"OK  {used_date}  |  ${price:,.1f}")
    print(f"    RSI: {output['rsi']} ({rsi_label})  |  MACD hist: {output['macd_hist']:+.3f}")
    print(f"    BB:  ${bb_lower:,.1f} / ${bb_mid:,.1f} / ${bb_upper:,.1f}  ({bb_pct:.1f}% of band)")
    print(f"    ATR: ${atr:.1f} ({atr_pct:.2f}%)")


if __name__ == "__main__":
    main()
