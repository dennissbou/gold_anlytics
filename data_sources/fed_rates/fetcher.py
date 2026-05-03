import requests
import psycopg2
import os
import time
from datetime import date
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "gold_analytics"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}

FRED_API_KEY = os.getenv("FRED_API_KEY")
FRED_BASE = "https://api.stlouisfed.org/fred"

SERIES = {
    "FEDFUNDS": "Federal Funds Effective Rate",
    "DFF":      "Federal Funds Effective Rate (Daily)",
    "CPIAUCSL": "CPI All Urban Consumers",
    "GS10":     "10-Year Treasury Yield",
    "GS2":      "2-Year Treasury Yield",
    "T10Y2Y":   "10Y-2Y Yield Spread",
    "DFII10":   "10-Year Real Interest Rate (TIPS)",
}


def _fred_get(url: str, params: dict, retries: int = 3, backoff: float = 2.0) -> requests.Response:
    """GET with retry on 5xx responses."""
    for attempt in range(retries):
        r = requests.get(url, params=params, timeout=15)
        if r.status_code < 500:
            r.raise_for_status()
            return r
        if attempt < retries - 1:
            time.sleep(backoff * (attempt + 1))
    r.raise_for_status()
    return r


def get_series_meta(series_id: str) -> dict:
    r = _fred_get(f"{FRED_BASE}/series", {"series_id": series_id, "api_key": FRED_API_KEY, "file_type": "json"})
    return r.json()["seriess"][0]


def get_latest_date(cur, series_id: str) -> date | None:
    cur.execute("SELECT MAX(date) FROM fed_rates.observations WHERE series_id = %s", (series_id,))
    return cur.fetchone()[0]


def fetch_observations(series_id: str, observation_start: str | None = None) -> list[dict]:
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "asc",
        "limit": 100000,
    }
    if observation_start:
        params["observation_start"] = observation_start

    r = _fred_get(f"{FRED_BASE}/series/observations", params, retries=3, backoff=2.0)

    records = []
    for obs in r.json()["observations"]:
        if obs["value"] == ".":   # FRED uses "." for missing values
            continue
        records.append({
            "series_id": series_id,
            "date": obs["date"],
            "value": float(obs["value"]),
        })
    return records


def upsert_series_meta(cur, series_id: str):
    meta = get_series_meta(series_id)
    cur.execute(
        """
        INSERT INTO fed_rates.series (id, title, frequency, units)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, updated_at = CURRENT_TIMESTAMP
        """,
        (series_id, meta["title"], meta["frequency"], meta["units"]),
    )


def update_series(cur, series_id: str) -> int:
    upsert_series_meta(cur, series_id)

    latest = get_latest_date(cur, series_id)
    if latest:
        from datetime import timedelta
        start = latest.strftime("%Y-%m-%d")  # re-fetch latest row — value may be revised
        print(f"  {series_id}: latest {latest} — re-fetching from {start}")
    else:
        start = None
        print(f"  {series_id}: no data — fetching full history")

    records = fetch_observations(series_id, start)

    if not records:
        print(f"  {series_id}: already up to date")
        return 0

    inserted = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO fed_rates.observations (series_id, date, value)
            VALUES (%(series_id)s, %(date)s, %(value)s)
            ON CONFLICT (series_id, date) DO UPDATE SET
                value = EXCLUDED.value
            """,
            r,
        )
        inserted += cur.rowcount

    return inserted


if __name__ == "__main__":
    print("Updating fed_rates...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    total = 0
    for series_id in SERIES:
        inserted = update_series(cur, series_id)
        if inserted:
            print(f"  {series_id}: inserted {inserted} rows")
        total += inserted

    conn.commit()
    cur.close()
    conn.close()
    print(f"Done. Total inserted: {total}")
