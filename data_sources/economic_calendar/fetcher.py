import requests
import psycopg2
import os
import time
from datetime import date, timedelta
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

# Key economic releases: FRED release_id -> (event_name, series_id_for_actual_value)
RELEASES = {
    10:  ("CPI",             "CPIAUCSL"),    # Consumer Price Index
    50:  ("NFP",             "PAYEMS"),      # Nonfarm Payrolls
    103: ("FOMC",            "FEDFUNDS"),    # Fed Funds Rate decision
    53:  ("GDP",             "GDPC1"),       # Real GDP
    46:  ("PPI",             "PPIACO"),      # Producer Price Index
    175: ("PCE",             "PCEPI"),       # PCE Price Index
}

YEARS_BACK = 3


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


def fetch_release_dates(release_id: int) -> list[str]:
    """Get all release dates (past + future) from FRED."""
    cutoff = (date.today() - timedelta(days=365 * YEARS_BACK)).strftime("%Y-%m-%d")
    params = {
        "release_id": release_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "limit": 1000,
        "sort_order": "asc",
        "include_release_dates_with_no_data": "true",
        # realtime_start omitted — it applies to metadata vintage, not event dates,
        # and causes FRED 500s on some releases when combined with include_no_data=true.
    }
    r = _fred_get(f"{FRED_BASE}/release/dates", params)
    all_dates = [d["date"] for d in r.json().get("release_dates", [])]
    return [d for d in all_dates if d >= cutoff]


def fetch_series_observations(series_id: str) -> dict[str, float]:
    """Get all observations for a FRED series as {date: value}."""
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "asc",
        "observation_start": (date.today() - timedelta(days=365 * YEARS_BACK)).strftime("%Y-%m-%d"),
    }
    r = _fred_get(f"{FRED_BASE}/series/observations", params)
    return {
        obs["date"]: float(obs["value"])
        for obs in r.json().get("observations", [])
        if obs["value"] != "."
    }


def build_records(release_id: int, event_name: str, series_id: str) -> list[dict]:
    release_dates = fetch_release_dates(release_id)
    actuals = fetch_series_observations(series_id)

    # For each release date, find the closest actual observation
    # Observations are published on or shortly after the release date
    sorted_obs_dates = sorted(actuals.keys())

    records = []
    for i, release_date in enumerate(release_dates):
        # Find actual value: observation published on or just before release date
        actual = None
        previous = None

        # Match observation to release date (within 7 days after)
        for obs_date in sorted_obs_dates:
            if obs_date <= release_date:
                actual_candidate = actuals[obs_date]
                if actual is None:
                    actual = actual_candidate
                else:
                    actual = actual_candidate  # keep updating to closest

        # Previous = value from the prior release
        if i > 0:
            prev_release = release_dates[i - 1]
            for obs_date in sorted_obs_dates:
                if obs_date <= prev_release:
                    previous = actuals[obs_date]

        records.append({
            "event_date":   release_date,
            "event_name":   event_name,
            "country":      "US",
            "impact":       "high",
            "actual":       actual,
            "forecast":     None,   # FRED doesn't provide forecasts
            "previous":     previous,
            "source":       "FRED",
            "fred_series":  series_id,
        })

    return records


def save_to_db(cur, records: list[dict]) -> int:
    inserted = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO economic_calendar.events
                (event_date, event_name, country, impact, actual, forecast, previous, source, fred_series)
            VALUES
                (%(event_date)s, %(event_name)s, %(country)s, %(impact)s, %(actual)s,
                 %(forecast)s, %(previous)s, %(source)s, %(fred_series)s)
            ON CONFLICT (event_date, event_name, country) DO UPDATE SET
                actual      = EXCLUDED.actual,
                previous    = EXCLUDED.previous,
                source      = EXCLUDED.source,
                fred_series = EXCLUDED.fred_series,
                created_at  = CURRENT_TIMESTAMP
            """,
            r,
        )
        inserted += cur.rowcount
    return inserted


if __name__ == "__main__":
    print("Updating economic_calendar.events (FRED)...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    today = date.today()
    total = 0

    for release_id, (event_name, series_id) in RELEASES.items():
        print(f"  {event_name} (release_id={release_id}, series={series_id})...", end=" ")
        try:
            records = build_records(release_id, event_name, series_id)
            inserted = save_to_db(cur, records)
            upcoming = sum(1 for r in records if r["event_date"] > str(today))
            past = len(records) - upcoming
            print(f"{past} past + {upcoming} upcoming -> {inserted} upserted")
            total += inserted
        except Exception as e:
            print(f"SKIPPED ({e})")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone. Total upserted: {total}")

    # Show upcoming events
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT event_date, event_name, actual
        FROM economic_calendar.events
        WHERE event_date >= %s
        ORDER BY event_date
        LIMIT 10
    """, (today,))
    print("\nUpcoming scheduled releases:")
    for row in cur.fetchall():
        status = f"actual={row[2]}" if row[2] is not None else "pending"
        print(f"  {row[0]} | {row[1]:8} | {status}")
    cur.close()
    conn.close()
