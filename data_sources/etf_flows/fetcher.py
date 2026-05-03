import requests
import psycopg2
import os
from datetime import date, datetime, timezone
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "gold_analytics"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}

WGC_HOLDINGS_URL = "https://fsapi.gold.org/api/v11/charts/etfv2/revised/holdings-chart2?break-cache=23Dec24"
WGC_FLOWS_URL    = "https://fsapi.gold.org/api/v11/charts/etfv2/revised/flows-chart2?break-cache=25Jul22"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def ms_to_date(ms: int) -> date:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().replace(day=1)


def fetch_holdings() -> list[dict]:
    r = requests.get(WGC_HOLDINGS_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()

    rows = r.json()["chartData"]["data"]["Monthly"]["tonnes"]["set"]
    records = []
    for row in rows:
        ts, n_am, eur, asia, other, gold_price = row[0], row[1], row[2], row[3], row[4], row[5]
        regions = [n_am, eur, asia, other]
        total = sum(v for v in regions if v is not None)
        records.append({
            "month":          ms_to_date(ts),
            "north_america":  n_am,
            "europe":         eur,
            "asia":           asia,
            "other":          other,
            "total":          round(total, 2) if total else None,
            "gold_price_usd": gold_price,
        })
    return records


def fetch_flows() -> list[dict]:
    r = requests.get(WGC_FLOWS_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()

    series = r.json()["chartData"]["data"]["Monthly"]["series"]["usd"]
    region_map = {s["name"]: s["data"] for s in series}

    # Align all regions by timestamp
    timestamps = sorted(set(row[0] for rows in region_map.values() for row in rows))
    index = {name: {row[0]: row[1] for row in rows} for name, rows in region_map.items()}

    records = []
    for ts in timestamps:
        n_am  = index.get("North America", {}).get(ts)
        eur   = index.get("Europe", {}).get(ts)
        asia  = index.get("Asia", {}).get(ts)
        other = index.get("Other", {}).get(ts)
        regions = [n_am, eur, asia, other]
        total = sum(v for v in regions if v is not None)
        records.append({
            "month":         ms_to_date(ts),
            "north_america": n_am,
            "europe":        eur,
            "asia":          asia,
            "other":         other,
            "total":         round(total, 2) if total else None,
        })
    return records


def save_holdings(cur, records: list[dict]) -> int:
    inserted = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO etf_flows.holdings_monthly
                (month, north_america, europe, asia, other, total, gold_price_usd)
            VALUES
                (%(month)s, %(north_america)s, %(europe)s, %(asia)s, %(other)s, %(total)s, %(gold_price_usd)s)
            ON CONFLICT (month) DO UPDATE SET
                north_america  = EXCLUDED.north_america,
                europe         = EXCLUDED.europe,
                asia           = EXCLUDED.asia,
                other          = EXCLUDED.other,
                total          = EXCLUDED.total,
                gold_price_usd = EXCLUDED.gold_price_usd,
                created_at     = CURRENT_TIMESTAMP
            """,
            r,
        )
        inserted += cur.rowcount
    return inserted


def save_flows(cur, records: list[dict]) -> int:
    inserted = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO etf_flows.flows_monthly
                (month, north_america, europe, asia, other, total)
            VALUES
                (%(month)s, %(north_america)s, %(europe)s, %(asia)s, %(other)s, %(total)s)
            ON CONFLICT (month) DO UPDATE SET
                north_america = EXCLUDED.north_america,
                europe        = EXCLUDED.europe,
                asia          = EXCLUDED.asia,
                other         = EXCLUDED.other,
                total         = EXCLUDED.total,
                created_at    = CURRENT_TIMESTAMP
            """,
            r,
        )
        inserted += cur.rowcount
    return inserted


if __name__ == "__main__":
    print("Updating etf_flows (World Gold Council API)...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("  Fetching holdings...")
    holdings = fetch_holdings()
    h_inserted = save_holdings(cur, holdings)
    print(f"  Holdings: {len(holdings)} rows fetched, {h_inserted} upserted")

    print("  Fetching flows...")
    flows = fetch_flows()
    f_inserted = save_flows(cur, flows)
    print(f"  Flows: {len(flows)} rows fetched, {f_inserted} upserted")

    conn.commit()
    cur.close()
    conn.close()

    # Print latest snapshot
    latest = holdings[-1] if holdings else {}
    print(f"\nLatest holdings ({latest.get('month')}):")
    print(f"  North America: {latest.get('north_america'):.1f}t")
    print(f"  Europe:        {latest.get('europe'):.1f}t")
    print(f"  Asia:          {latest.get('asia'):.1f}t")
    print(f"  Other:         {latest.get('other'):.1f}t")
    print(f"  Total:         {latest.get('total'):.1f}t")
    print(f"  Gold price:    ${latest.get('gold_price_usd'):.2f}/oz")
