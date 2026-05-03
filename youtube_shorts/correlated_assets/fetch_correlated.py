#!/usr/bin/env python3
"""
Fetch yesterday's % change for all correlated assets + Gold and export to public/data.json.

Assets:
  GOLD   — gold_prices.gold_prices_1d
  SILVER, DXY, WTI, SPX, US10Y, VIX — correlated_assets.prices_1d

Usage:
    python fetch_correlated.py                    # Latest available date in DB
    python fetch_correlated.py --date 2026-03-27  # Specific date
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


# Display metadata per symbol
ASSET_META = {
    "GOLD":   {"name": "Gold",              "label": "XAU/USD"},
    "SILVER": {"name": "Silver",            "label": "XAG/USD"},
    "DXY":    {"name": "US Dollar Index",   "label": "DXY"},
    "WTI":    {"name": "Crude Oil",         "label": "WTI"},
    "SPX":    {"name": "S&P 500",           "label": "SPX"},
    "BTC":    {"name": "Bitcoin",            "label": "BTC/USD"},
    "VIX":    {"name": "Volatility Index",  "label": "VIX"},
}

# Fixed display order
ASSET_ORDER = ["GOLD", "SILVER", "DXY", "WTI", "SPX", "BTC", "VIX"]


def fetch_last_two(cur, table: str, symbol_col: str, symbol: str, target_date: str = None) -> tuple:
    """Return (date, close, prev_close) for the two most recent rows up to target_date."""
    if target_date:
        cur.execute(f"""
            SELECT timestamp::date, close
            FROM {table}
            {"WHERE " + symbol_col + " = %s AND" if symbol_col else "WHERE"} timestamp::date <= %s
            ORDER BY timestamp DESC LIMIT 2
        """, (symbol, target_date) if symbol_col else (target_date,))
    else:
        if symbol_col:
            cur.execute(f"""
                SELECT timestamp::date, close
                FROM {table}
                WHERE {symbol_col} = %s
                ORDER BY timestamp DESC LIMIT 2
            """, (symbol,))
        else:
            cur.execute(f"""
                SELECT timestamp::date, close
                FROM {table}
                ORDER BY timestamp DESC LIMIT 2
            """)

    rows = cur.fetchall()
    if len(rows) < 2:
        return None, None, None
    return rows[0][0], float(rows[0][1]), float(rows[1][1])


def fetch_gold_from_1h(cur, target_date: str = None) -> tuple:
    """Return (date, close, prev_close) for gold using last hourly candle per day."""
    if target_date:
        cur.execute("""
            SELECT timestamp::date AS day, close
            FROM gold_prices.gold_prices_1h
            WHERE timestamp::date <= %s
            ORDER BY timestamp DESC LIMIT 1
        """, (target_date,))
    else:
        cur.execute("""
            SELECT timestamp::date AS day, close
            FROM gold_prices.gold_prices_1h
            ORDER BY timestamp DESC LIMIT 1
        """)
    row = cur.fetchone()
    if not row:
        return None, None, None
    gold_date, gold_close = row[0], float(row[1])

    # Fetch last candle of the day before gold_date
    cur.execute("""
        SELECT close
        FROM gold_prices.gold_prices_1h
        WHERE timestamp::date < %s
        ORDER BY timestamp DESC LIMIT 1
    """, (gold_date,))
    prev_row = cur.fetchone()
    if not prev_row:
        return gold_date, gold_close, None
    return gold_date, gold_close, float(prev_row[0])


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
    cur = conn.cursor()

    results = {}

    # Gold — use last hourly candle for consistency with rolling-candles frame
    gold_date, gold_close, gold_prev = fetch_gold_from_1h(cur, target_date)
    if gold_close and gold_prev:
        results["GOLD"] = {
            "date":       gold_date.isoformat() if gold_date else None,
            "close":      round(gold_close, 2),
            "prev_close": round(gold_prev, 2),
            "change_pct": round((gold_close - gold_prev) / gold_prev * 100, 2),
        }

    # Correlated assets
    for symbol in ["SILVER", "DXY", "WTI", "SPX", "BTC", "VIX"]:
        asset_date, close, prev = fetch_last_two(
            cur, "correlated_assets.prices_1d", "symbol", symbol, target_date
        )
        if close and prev:
            results[symbol] = {
                "date":       asset_date.isoformat() if asset_date else None,
                "close":      round(close, 4),
                "prev_close": round(prev, 4),
                "change_pct": round((close - prev) / prev * 100, 2),
            }

    cur.close()
    conn.close()

    # Determine display date (most common latest date)
    dates = [v["date"] for v in results.values() if v.get("date")]
    display_date = max(dates) if dates else (target_date or str(date.today()))

    # Build ordered asset list
    assets = []
    for symbol in ASSET_ORDER:
        meta = ASSET_META[symbol]
        if symbol in results:
            r = results[symbol]
            assets.append({
                "symbol":     symbol,
                "name":       meta["name"],
                "label":      meta["label"],
                "close":      r["close"],
                "prev_close": r["prev_close"],
                "change_pct": r["change_pct"],
                "date":       r["date"],
            })
        else:
            assets.append({
                "symbol":     symbol,
                "name":       meta["name"],
                "label":      meta["label"],
                "close":      None,
                "prev_close": None,
                "change_pct": None,
                "date":       None,
            })

    output = {"date": display_date, "assets": assets}

    output_path = os.path.join(os.path.dirname(__file__), "public", "data.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, cls=DecimalEncoder)

    print(f"OK  Correlated assets heatmap — {display_date}")
    for a in assets:
        if a["change_pct"] is not None:
            sign = "+" if a["change_pct"] >= 0 else ""
            print(f"   {a['symbol']:8s}  {a['close']:>10.4g}   {sign}{a['change_pct']:+.2f}%")
        else:
            print(f"   {a['symbol']:8s}  N/A")


if __name__ == "__main__":
    main()
