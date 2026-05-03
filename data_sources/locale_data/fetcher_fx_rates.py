"""
Fetches live FX rates for all goldprice.trade locales from the fawaz currency API
and stores daily snapshots in locale_data.fx_rates.

Smart insertion:
  - Detects the last date in the DB and backfills every missing calendar day up to today.
  - Caches fawaz API responses by (currency, date) so each unique date is only
    fetched once even when needed both as a "target date" and as a "30d-ago" date.
  - ON CONFLICT (fetched_date, locale) DO UPDATE keeps re-runs idempotent.

No API key required.
"""

import os
from datetime import date, timedelta

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

FAWAZ_BASE = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/v1/currencies"
REQUEST_TIMEOUT = 15

LOCALES = {
    "ar": "ARS",
    "br": "BRL",
    "cl": "CLP",
    "co": "COP",
    "cr": "CRC",
    "kz": "KZT",
    "mx": "MXN",
    "pe": "PEN",
    "uy": "UYU",
}

# In-process cache: (base_currency, date_str) → rates dict
_api_cache: dict[tuple[str, str], dict] = {}


def fawaz_get(base_currency: str, date_str: str) -> dict:
    key = (base_currency, date_str)
    if key in _api_cache:
        return _api_cache[key]

    url = f"{FAWAZ_BASE.format(date=date_str)}/{base_currency.lower()}.json"
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        rates = r.json().get(base_currency.lower(), {})
    except Exception as e:
        print(f"  [WARN] fawaz {base_currency} {date_str}: {e}")
        rates = {}

    _api_cache[key] = rates
    return rates


def compute_trend(change_30d: float | None) -> str | None:
    if change_30d is None:
        return None
    if change_30d > 2:
        return "weakening"
    if change_30d < -2:
        return "strengthening"
    return "stable"


def get_missing_dates(conn) -> list[str]:
    """
    Return every calendar date from (last DB date + 1 day) to today, inclusive.
    Returns [today] on first run (empty DB).
    Returns [] if already up to date.
    """
    cur = conn.cursor()
    cur.execute("SELECT MAX(fetched_date) FROM locale_data.fx_rates")
    last_date = cur.fetchone()[0]
    cur.close()

    today = date.today()

    if last_date is None:
        return [today.isoformat()]

    if last_date >= today:
        return []

    missing = []
    d = last_date + timedelta(days=1)
    while d <= today:
        missing.append(d.isoformat())
        d += timedelta(days=1)
    return missing


def build_records_for_date(date_str: str) -> list[dict]:
    """Fetch fawaz rates for date_str and its 30-days-prior anchor, return insert records."""
    target = date.fromisoformat(date_str)
    anchor_str = (target - timedelta(days=30)).isoformat()

    usd_target = fawaz_get("usd", date_str)
    usd_anchor = fawaz_get("usd", anchor_str)
    xau_target = fawaz_get("xau", date_str)

    if not usd_target:
        print(f"  [SKIP] {date_str}: fawaz returned no USD rates (date may not be available yet)")
        return []

    gold_price_usd = xau_target.get("usd")

    records = []
    for locale, currency in LOCALES.items():
        code = currency.lower()
        rate_target = usd_target.get(code)
        rate_anchor = usd_anchor.get(code)
        gold_local  = xau_target.get(code)

        if rate_target is None:
            print(f"  [WARN] {date_str} {locale.upper()}: no rate for {currency}")
            continue

        change_30d = None
        if rate_anchor and rate_anchor != 0:
            change_30d = round((rate_target - rate_anchor) / rate_anchor * 100, 4)

        records.append({
            "fetched_date":    date_str,
            "locale":          locale,
            "currency":        currency,
            "rate_usd":        round(rate_target, 6),
            "change_30d_pct":  change_30d,
            "fx_trend":        compute_trend(change_30d),
            "gold_price_usd":  round(gold_price_usd, 4) if gold_price_usd else None,
            "gold_price_local": round(gold_local, 4) if gold_local else None,
        })

    # Panama — dollarized, always 1:1
    records.append({
        "fetched_date":    date_str,
        "locale":          "pa",
        "currency":        "USD",
        "rate_usd":        1.0,
        "change_30d_pct":  0.0,
        "fx_trend":        "stable",
        "gold_price_usd":  round(gold_price_usd, 4) if gold_price_usd else None,
        "gold_price_local": round(gold_price_usd, 4) if gold_price_usd else None,
    })

    return records


def save_to_db(conn, records: list[dict]) -> int:
    cur = conn.cursor()
    upserted = 0

    for r in records:
        cur.execute(
            """
            INSERT INTO locale_data.fx_rates
                (fetched_date, locale, currency, rate_usd, change_30d_pct, fx_trend,
                 gold_price_usd, gold_price_local)
            VALUES
                (%(fetched_date)s, %(locale)s, %(currency)s, %(rate_usd)s,
                 %(change_30d_pct)s, %(fx_trend)s, %(gold_price_usd)s, %(gold_price_local)s)
            ON CONFLICT (fetched_date, locale) DO UPDATE SET
                rate_usd         = EXCLUDED.rate_usd,
                change_30d_pct   = EXCLUDED.change_30d_pct,
                fx_trend         = EXCLUDED.fx_trend,
                gold_price_usd   = EXCLUDED.gold_price_usd,
                gold_price_local = EXCLUDED.gold_price_local,
                created_at       = CURRENT_TIMESTAMP
            """,
            r,
        )
        upserted += cur.rowcount

    conn.commit()
    cur.close()
    return upserted


if __name__ == "__main__":
    conn = psycopg2.connect(**DB_CONFIG)

    missing_dates = get_missing_dates(conn)

    if not missing_dates:
        print("FX rates already up to date — nothing to fetch")
        conn.close()
        raise SystemExit(0)

    today = date.today().isoformat()
    print(f"Missing {len(missing_dates)} date(s): {missing_dates[0]} → {missing_dates[-1]}")

    total_upserted = 0
    total_records  = 0

    for date_str in missing_dates:
        records = build_records_for_date(date_str)
        if not records:
            continue

        upserted = save_to_db(conn, records)
        total_upserted += upserted
        total_records  += len(records)

        gold_usd = records[0].get("gold_price_usd")
        gold_str = f"  gold=${gold_usd:,.2f}" if gold_usd else ""
        print(f"  {date_str}: {upserted}/{len(records)} rows upserted{gold_str}")

    conn.close()
    print(f"\nDone — {total_upserted}/{total_records} rows upserted across {len(missing_dates)} date(s)")
