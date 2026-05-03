import requests
import psycopg2
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

_session = requests.Session()
_session.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "gold_analytics"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}

TICKER = "GC=F"        # Gold Futures
YEARS_BACK = 5

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def get_latest_timestamp(cur) -> datetime | None:
    cur.execute("SELECT MAX(timestamp) FROM gold_prices.gold_prices_1d")
    result = cur.fetchone()[0]
    return result


def fetch_gold_prices(start: datetime, end: datetime) -> list[dict]:
    url = YAHOO_URL.format(ticker=TICKER)
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
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        if None in (o, h, l, c):
            continue
        records.append({
            "timestamp": datetime.utcfromtimestamp(ts).replace(hour=0, minute=0, second=0, microsecond=0),
            "open":   round(float(o), 1),
            "high":   round(float(h), 1),
            "low":    round(float(l), 1),
            "close":  round(float(c), 1),
            "volume": float(volumes[i]) if volumes[i] else None,
        })

    return records


def save_to_db(records: list[dict]) -> int:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    latest = get_latest_timestamp(cur)

    if latest is None:
        start = datetime.today() - timedelta(days=365 * YEARS_BACK)
        print(f"  No existing data — fetching full {YEARS_BACK}y history")
    else:
        start = latest  # re-fetch latest row — it may have been a partial candle
        print(f"  Latest in DB: {latest.date()} — re-fetching from {start.date()}")

    end = datetime.today()
    records = fetch_gold_prices(start, end)

    if not records:
        print("  Already up to date, nothing to insert")
        cur.close()
        conn.close()
        return 0

    inserted = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO gold_prices.gold_prices_1d (timestamp, open, high, low, close, volume)
            VALUES (%(timestamp)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s)
            ON CONFLICT (timestamp) DO UPDATE SET
                open   = EXCLUDED.open,
                high   = EXCLUDED.high,
                low    = EXCLUDED.low,
                close  = EXCLUDED.close,
                volume = EXCLUDED.volume
            """,
            r,
        )
        inserted += cur.rowcount

    conn.commit()
    cur.close()
    conn.close()
    return inserted


if __name__ == "__main__":
    print(f"Updating gold_prices.gold_prices_1d ({TICKER})...")
    inserted = save_to_db([])
    print(f"  Inserted {inserted} new rows")
