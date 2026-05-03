#!/usr/bin/env python3
"""
Fetch 7-day % change for correlated assets + Gold.

Compares the close on or before the anchor date against the close
on or before (anchor - 7 days). Anchor defaults to today.

Output: article_gifs/correlated-heatmap/public/data.json

Usage:
    python fetch_correlated_heatmap.py                    # anchor = today
    python fetch_correlated_heatmap.py --date 2026-04-11  # anchor = 2026-04-11
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal

import psycopg2
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


ASSET_META = {
    "GOLD":   {"name": "Gold",             "label": "XAU/USD"},
    "SILVER": {"name": "Silver",           "label": "XAG/USD"},
    "DXY":    {"name": "US Dollar Index",  "label": "DXY"},
    "WTI":    {"name": "Crude Oil",        "label": "WTI"},
    "SPX":    {"name": "S&P 500",          "label": "SPX"},
    "BTC":    {"name": "Bitcoin",          "label": "BTC/USD"},
    "VIX":    {"name": "Volatility Index", "label": "VIX"},
}

ASSET_ORDER = ["GOLD", "SILVER", "DXY", "WTI", "SPX", "BTC", "VIX"]


_MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def format_period(prev_date: date, this_date: date) -> str:
    """Return e.g. '03 Apr – 10 Apr' or '28 Mar – 04 Apr'."""
    def _fmt(d: date) -> str:
        return f"{d.day:02d} {_MONTHS[d.month - 1]}"
    return f"{_fmt(prev_date)} – {_fmt(this_date)}"


def get_close_on_or_before(cur, table: str, symbol_col: str | None,
                            symbol: str | None, cutoff: date):
    """Return (actual_date, close) for the last trading day on or before cutoff."""
    if symbol_col and symbol:
        cur.execute(f"""
            SELECT timestamp::date AS trade_date, close
            FROM {table}
            WHERE {symbol_col} = %s AND timestamp::date <= %s
            ORDER BY timestamp DESC LIMIT 1
        """, (symbol, cutoff))
    else:
        cur.execute(f"""
            SELECT timestamp::date AS trade_date, close
            FROM {table}
            WHERE timestamp::date <= %s
            ORDER BY timestamp DESC LIMIT 1
        """, (cutoff,))
    row = cur.fetchone()
    if not row:
        return None, None
    return row[0], float(row[1])


def main():
    # Determine anchor date (end of the 7-day window)
    if len(sys.argv) > 2 and sys.argv[1] == "--date":
        anchor = date.fromisoformat(sys.argv[2])
    else:
        anchor = date.today()

    this_date = anchor
    prev_date = this_date - timedelta(days=7)
    period    = format_period(prev_date, this_date)

    print(f"7-day period: {prev_date} to {this_date}  ({period})")

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "gold_analytics"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    cur = conn.cursor()

    results = {}

    # Gold — from gold_prices_1h for consistency with price-chart / technical-dashboard
    cur_date, cur_close = get_close_on_or_before(
        cur, "gold_prices.gold_prices_1h", None, None, this_date
    )
    _, prev_close = get_close_on_or_before(
        cur, "gold_prices.gold_prices_1h", None, None, prev_date
    )
    if cur_close and prev_close:
        results["GOLD"] = {
            "date":       cur_date.isoformat() if cur_date else None,
            "close":      round(cur_close, 2),
            "change_pct": round((cur_close - prev_close) / prev_close * 100, 2),
        }

    # Correlated assets
    for symbol in ["SILVER", "DXY", "WTI", "SPX", "BTC", "VIX"]:
        cur_date_a, cur_c = get_close_on_or_before(
            cur, "correlated_assets.prices_1d", "symbol", symbol, this_date
        )
        _,          prev_c = get_close_on_or_before(
            cur, "correlated_assets.prices_1d", "symbol", symbol, prev_date
        )
        if cur_c and prev_c:
            results[symbol] = {
                "date":       cur_date_a.isoformat() if cur_date_a else None,
                "close":      round(cur_c, 4),
                "change_pct": round((cur_c - prev_c) / prev_c * 100, 2),
            }

    cur.close()
    conn.close()

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
                "change_pct": r["change_pct"],
                "date":       r["date"],
            })
        else:
            assets.append({
                "symbol":     symbol,
                "name":       meta["name"],
                "label":      meta["label"],
                "close":      None,
                "change_pct": None,
                "date":       None,
            })

    output = {
        "date":      this_date.isoformat(),
        "prev_date": prev_date.isoformat(),
        "period":    period,
        "assets":    assets,
    }

    output_path = os.path.join(os.path.dirname(__file__), "public", "data.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, cls=DecimalEncoder)

    print(f"OK  {period}")
    for a in assets:
        if a["change_pct"] is not None:
            print(f"   {a['symbol']:8s}  {a['close']:>12.4g}   {a['change_pct']:+.2f}%")
        else:
            print(f"   {a['symbol']:8s}  N/A")


if __name__ == "__main__":
    main()
