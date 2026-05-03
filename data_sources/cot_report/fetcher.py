import requests
import psycopg2
import zipfile
import io
import csv
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

CFTC_URL = "https://www.cftc.gov/files/dea/history/deacot{year}.zip"
MARKET_NAME = "GOLD - COMMODITY EXCHANGE INC."
HEADERS = {"User-Agent": "Mozilla/5.0"}
YEARS_BACK = 5


def fetch_year(year: int) -> list[dict]:
    url = CFTC_URL.format(year=year)
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()

    z = zipfile.ZipFile(io.BytesIO(r.content))
    records = []

    with z.open("annual.txt") as f:
        text = io.TextIOWrapper(f, encoding="utf-8")
        reader = csv.DictReader(text)

        for row in reader:
            if row.get("Market and Exchange Names", "").strip() != MARKET_NAME:
                continue

            report_date = row["As of Date in Form YYYY-MM-DD"].strip()
            if not report_date:
                continue

            noncomm_long  = int(row["Noncommercial Positions-Long (All)"].replace(",", ""))
            noncomm_short = int(row["Noncommercial Positions-Short (All)"].replace(",", ""))
            comm_long     = int(row["Commercial Positions-Long (All)"].replace(",", ""))
            comm_short    = int(row["Commercial Positions-Short (All)"].replace(",", ""))

            records.append({
                "report_date":  report_date,
                "open_interest": int(row["Open Interest (All)"].replace(",", "")),
                "noncomm_long":  noncomm_long,
                "noncomm_short": noncomm_short,
                "noncomm_net":   noncomm_long - noncomm_short,
                "comm_long":     comm_long,
                "comm_short":    comm_short,
                "comm_net":      comm_long - comm_short,
            })

    return records


def get_latest_date(cur) -> date | None:
    cur.execute("SELECT MAX(report_date) FROM cot_report.gold_futures")
    return cur.fetchone()[0]


def save_to_db(cur, records: list[dict]) -> int:
    inserted = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO cot_report.gold_futures
                (report_date, open_interest, noncomm_long, noncomm_short, noncomm_net, comm_long, comm_short, comm_net)
            VALUES
                (%(report_date)s, %(open_interest)s, %(noncomm_long)s, %(noncomm_short)s, %(noncomm_net)s,
                 %(comm_long)s, %(comm_short)s, %(comm_net)s)
            ON CONFLICT (report_date) DO UPDATE SET
                open_interest  = EXCLUDED.open_interest,
                noncomm_long   = EXCLUDED.noncomm_long,
                noncomm_short  = EXCLUDED.noncomm_short,
                noncomm_net    = EXCLUDED.noncomm_net,
                comm_long      = EXCLUDED.comm_long,
                comm_short     = EXCLUDED.comm_short,
                comm_net       = EXCLUDED.comm_net
            """,
            r,
        )
        inserted += cur.rowcount
    return inserted


if __name__ == "__main__":
    print("Updating cot_report.gold_futures (CFTC)...")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    latest = get_latest_date(cur)

    current_year = date.today().year
    start_year = current_year - YEARS_BACK if latest is None else latest.year

    print(f"  Latest in DB: {latest} — fetching from {start_year}")

    total = 0
    for year in range(start_year, current_year + 1):
        print(f"  Fetching {year}...", end=" ")
        try:
            records = fetch_year(year)
            # latest row is included — save_to_db uses DO UPDATE to replace it
            inserted = save_to_db(cur, records)
            print(f"{len(records)} rows fetched, {inserted} inserted")
            total += inserted
        except requests.HTTPError as e:
            print(f"SKIP ({e})")

    conn.commit()
    cur.close()
    conn.close()
    print(f"Done. Total inserted: {total}")
