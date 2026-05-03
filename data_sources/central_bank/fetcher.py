import requests
import psycopg2
import os
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

# World Bank API — no auth required, annual frequency
WB_URL = "https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}?format=json&per_page=500&mrv=10"

TROY_OZ_PER_TONNE = 32_150.746

COUNTRIES = ["US", "CN", "DE", "IT", "FR", "RU", "IN", "TR", "PL", "SG"]

COUNTRY_NAMES = {
    "US": "United States", "CN": "China",    "DE": "Germany",
    "IT": "Italy",         "FR": "France",   "RU": "Russia",
    "IN": "India",         "TR": "Turkey",   "PL": "Poland",
    "SG": "Singapore",
}


def fetch_wb_indicator(indicator: str) -> dict[str, dict[str, float]]:
    """Returns {country_code: {year_str: value}}"""
    countries_str = ";".join(COUNTRIES)
    url = WB_URL.format(countries=countries_str, indicator=indicator)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    if len(data) < 2 or not data[1]:
        return {}

    result: dict[str, dict[str, float]] = {}
    for row in data[1]:
        if row["value"] is None:
            continue
        code = row["country"]["id"]
        year = row["date"]
        result.setdefault(code, {})[year] = float(row["value"])

    return result


def get_year_end_gold_prices(cur) -> dict[int, float]:
    """Returns {year: close_price} using last trading day of each year from DB."""
    cur.execute("""
        SELECT EXTRACT(YEAR FROM timestamp)::int AS yr, close
        FROM gold_prices.gold_prices_1d
        WHERE timestamp IN (
            SELECT MAX(timestamp)
            FROM gold_prices.gold_prices_1d
            GROUP BY EXTRACT(YEAR FROM timestamp)
        )
        ORDER BY yr
    """)
    return {row[0]: float(row[1]) for row in cur.fetchall()}


def build_records(total: dict, excl: dict, gold_prices: dict[int, float]) -> list[dict]:
    records = []
    for country in COUNTRIES:
        total_by_year = total.get(country, {})
        excl_by_year = excl.get(country, {})

        for year_str in total_by_year:
            if year_str not in excl_by_year:
                continue
            year = int(year_str)
            gold_usd = total_by_year[year_str] - excl_by_year[year_str]
            if gold_usd <= 0:
                continue

            # Use year-end gold price; fallback to nearest available year
            price = gold_prices.get(year) or gold_prices.get(year - 1)
            if not price:
                continue

            troy_oz = gold_usd / price
            tonnes = round(troy_oz / TROY_OZ_PER_TONNE, 2)

            records.append({
                "month": date(year, 12, 31),
                "country": country,
                "tonnes": tonnes,
            })

    return records


def save_to_db(records: list[dict]) -> int:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    gold_prices = get_year_end_gold_prices(cur)
    print(f"  Year-end gold prices available: {sorted(gold_prices.keys())}")

    total = fetch_wb_indicator("FI.RES.TOTL.CD")
    excl  = fetch_wb_indicator("FI.RES.XGLD.CD")

    records = build_records(total, excl, gold_prices)

    inserted = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO central_bank.gold_reserves (month, country, tonnes)
            VALUES (%(month)s, %(country)s, %(tonnes)s)
            ON CONFLICT (month, country) DO UPDATE SET
                tonnes     = EXCLUDED.tonnes,
                created_at = CURRENT_TIMESTAMP
            """,
            r,
        )
        inserted += cur.rowcount

    conn.commit()
    cur.close()
    conn.close()
    return inserted


if __name__ == "__main__":
    print("Fetching central bank gold reserves (World Bank API)...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    gold_prices = get_year_end_gold_prices(cur)
    cur.close()
    conn.close()
    print(f"  Year-end gold prices available: {sorted(gold_prices.keys())}")

    print("  Fetching World Bank indicators...")
    total = fetch_wb_indicator("FI.RES.TOTL.CD")
    excl  = fetch_wb_indicator("FI.RES.XGLD.CD")

    records = build_records(total, excl, gold_prices)
    print(f"  Built {len(records)} records across {len(COUNTRIES)} countries")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    inserted = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO central_bank.gold_reserves (month, country, tonnes)
            VALUES (%(month)s, %(country)s, %(tonnes)s)
            ON CONFLICT (month, country) DO UPDATE SET
                tonnes     = EXCLUDED.tonnes,
                created_at = CURRENT_TIMESTAMP
            """,
            r,
        )
        inserted += cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    print(f"  Upserted {inserted} rows into central_bank.gold_reserves")

    # Print latest snapshot
    latest = {}
    for r in records:
        c = r["country"]
        if c not in latest or r["month"] > latest[c]["month"]:
            latest[c] = r
    print("\nLatest holdings (approx, derived from World Bank annual data):")
    for code, r in sorted(latest.items(), key=lambda x: -x[1]["tonnes"]):
        name = COUNTRY_NAMES.get(code, code)
        print(f"  {name:20s} ({code})  {r['tonnes']:>8.1f}t  [{r['month'].year}]")
