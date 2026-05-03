"""
Fetches annual macro indicators (inflation, GDP growth) for all goldprice.trade
locales from the World Bank API and upserts into locale_data.macro.

Smart insertion:
  - Skips the World Bank API entirely if all locales were updated within the last
    REFRESH_INTERVAL_DAYS days. World Bank data is annual — daily re-fetching
    returns identical values and wastes time.
  - Re-fetches only when the oldest locale record is stale.

No API key required.
"""

import os
from datetime import datetime, timedelta, timezone

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "127.0.0.1"),
    "port":     os.getenv("DB_PORT", "5432"),
    "dbname":   os.getenv("DB_NAME", "gold_analytics"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}

WORLDBANK_BASE = "https://api.worldbank.org/v2/country/{iso2}/indicator/{indicator}?format=json&mrv=3"
REQUEST_TIMEOUT = 15
REFRESH_INTERVAL_DAYS = 7   # only re-fetch from World Bank if oldest record is older than this

LOCALES = {
    "en": "US",
    "ar": "AR",
    "br": "BR",
    "cl": "CL",
    "co": "CO",
    "cr": "CR",
    "kz": "KZ",
    "mx": "MX",
    "pa": "PA",
    "pe": "PE",
    "uy": "UY",
}

INDICATORS = {
    "inflation":  "FP.CPI.TOTL.ZG",    # Annual CPI %
    "gdp_growth": "NY.GDP.MKTP.KD.ZG",  # Real GDP growth %
}


def is_fresh(conn) -> bool:
    """
    Return True if every locale has been updated within REFRESH_INTERVAL_DAYS.
    Also returns True if the table has all expected locales populated.
    """
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), MIN(updated_at) FROM locale_data.macro")
    count, oldest = cur.fetchone()
    cur.close()

    if count < len(LOCALES):
        return False  # missing locales — must fetch

    if oldest is None:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(days=REFRESH_INTERVAL_DAYS)
    # oldest may be naive (no tz from postgres default) — normalise
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)

    return oldest >= cutoff


def worldbank_latest(iso2: str, indicator: str) -> tuple[float | None, int | None]:
    url = WORLDBANK_BASE.format(iso2=iso2.lower(), indicator=indicator)
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if len(data) < 2 or not data[1]:
            return None, None
        for entry in data[1]:
            if entry.get("value") is not None:
                return round(entry["value"], 4), int(entry["date"])
    except Exception as e:
        print(f"  [WARN] World Bank {iso2} {indicator}: {e}")
    return None, None


def save_to_db(conn, records: list[dict]) -> int:
    cur = conn.cursor()
    upserted = 0

    for r in records:
        cur.execute(
            """
            INSERT INTO locale_data.macro
                (locale, iso2, inflation_annual_pct, inflation_year,
                 gdp_growth_pct, gdp_year, updated_at)
            VALUES
                (%(locale)s, %(iso2)s, %(inflation_annual_pct)s, %(inflation_year)s,
                 %(gdp_growth_pct)s, %(gdp_year)s, CURRENT_TIMESTAMP)
            ON CONFLICT (locale) DO UPDATE SET
                inflation_annual_pct = EXCLUDED.inflation_annual_pct,
                inflation_year       = EXCLUDED.inflation_year,
                gdp_growth_pct       = EXCLUDED.gdp_growth_pct,
                gdp_year             = EXCLUDED.gdp_year,
                updated_at           = CURRENT_TIMESTAMP
            """,
            r,
        )
        upserted += cur.rowcount

    conn.commit()
    cur.close()
    return upserted


if __name__ == "__main__":
    conn = psycopg2.connect(**DB_CONFIG)

    if is_fresh(conn):
        print(f"Macro data is fresh (updated within {REFRESH_INTERVAL_DAYS}d) — skipping World Bank fetch")
        conn.close()
        raise SystemExit(0)

    print("Fetching World Bank macro indicators (inflation, GDP) for all locales...")
    records = []

    for locale, iso2 in LOCALES.items():
        inflation, inf_year  = worldbank_latest(iso2, INDICATORS["inflation"])
        gdp_growth, gdp_year = worldbank_latest(iso2, INDICATORS["gdp_growth"])

        records.append({
            "locale":               locale,
            "iso2":                 iso2,
            "inflation_annual_pct": inflation,
            "inflation_year":       inf_year,
            "gdp_growth_pct":       gdp_growth,
            "gdp_year":             gdp_year,
        })

        inf_str = f"{inflation:+.2f}% ({inf_year})" if inflation is not None else "n/a"
        gdp_str = f"{gdp_growth:+.2f}% ({gdp_year})" if gdp_growth is not None else "n/a"
        print(f"  {locale.upper()} ({iso2}): inflation={inf_str}  GDP={gdp_str}")

    upserted = save_to_db(conn, records)
    conn.close()
    print(f"\nUpserted {upserted}/{len(records)} rows into locale_data.macro")
