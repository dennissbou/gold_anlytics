import requests
import psycopg2
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "gold_analytics"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}

ASSETS = {
    "DXY":    "DX-Y.NYB",    # US Dollar Index (cash)
    "US10Y":  "^TNX",        # 10-Year Treasury Yield
    "WTI":    "CL=F",        # WTI Crude Oil Futures
    "BTC":    "BTC-USD",     # Bitcoin / USD
    "SILVER": "SI=F",        # Silver Futures
    "SPX":    "^GSPC",       # S&P 500
    "VIX":    "^VIX",        # Volatility Index
}

YEARS_BACK = 5

_session = requests.Session()
_session.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def get_latest_timestamp(cur, symbol: str) -> datetime | None:
    cur.execute(
        "SELECT MAX(timestamp) FROM correlated_assets.prices_1d WHERE symbol = %s",
        (symbol,)
    )
    return cur.fetchone()[0]


def fetch_asset(symbol: str, ticker: str, start: datetime, end: datetime) -> list[dict]:
    url = YAHOO_URL.format(ticker=ticker)
    params = {
        "interval": "1d",
        "period1": int(start.timestamp()),
        "period2": int(end.timestamp()),
    }
    resp = _session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    result = data.get("chart", {}).get("result")
    if not result:
        return []

    chart = result[0]
    timestamps = chart["timestamp"]
    quote = chart["indicators"]["quote"][0]
    opens   = quote.get("open", [])
    highs   = quote.get("high", [])
    lows    = quote.get("low", [])
    closes  = quote.get("close", [])
    volumes = quote.get("volume", [])

    records = []
    for i, ts in enumerate(timestamps):
        c = closes[i]
        if c is None:
            continue
        records.append({
            "timestamp": datetime.utcfromtimestamp(ts).replace(hour=0, minute=0, second=0, microsecond=0),
            "symbol": symbol,
            "open":   round(float(opens[i]), 4) if opens[i] else None,
            "high":   round(float(highs[i]), 4) if highs[i] else None,
            "low":    round(float(lows[i]), 4) if lows[i] else None,
            "close":  round(float(c), 4),
            "volume": float(volumes[i]) if volumes[i] else None,
        })

    return records


def update_asset(cur, symbol: str, ticker: str) -> int:
    latest = get_latest_timestamp(cur, symbol)
    end = datetime.today()

    if latest is None:
        start = end - timedelta(days=365 * YEARS_BACK)
        print(f"  {symbol}: no data — fetching full {YEARS_BACK}y history")
    else:
        start = latest  # re-fetch latest row — it may have been a partial candle
        print(f"  {symbol}: latest {latest.date()} — re-fetching from {start.date()}")

    records = fetch_asset(symbol, ticker, start, end)

    if not records:
        print(f"  {symbol}: already up to date")
        return 0

    inserted = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO correlated_assets.prices_1d (timestamp, symbol, open, high, low, close, volume)
            VALUES (%(timestamp)s, %(symbol)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s)
            ON CONFLICT (timestamp, symbol) DO UPDATE SET
                open   = EXCLUDED.open,
                high   = EXCLUDED.high,
                low    = EXCLUDED.low,
                close  = EXCLUDED.close,
                volume = EXCLUDED.volume
            """,
            r,
        )
        inserted += cur.rowcount

    return inserted


if __name__ == "__main__":
    print(f"Updating correlated_assets.prices_1d...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    total = 0
    for symbol, ticker in ASSETS.items():
        try:
            inserted = update_asset(cur, symbol, ticker)
        except Exception as e:
            print(f"  {symbol}: ERROR — {e}")
            inserted = 0
        if inserted:
            print(f"  {symbol}: inserted {inserted} new rows")
        total += inserted

    conn.commit()
    cur.close()
    conn.close()
    print(f"Done. Total inserted: {total}")
