"""
Fetches country-specific economic/gold news headlines for all locales via NewsAPI
and stores them in locale_data.news_headlines.

Smart insertion:
  - Cooldown check: if any headlines were inserted within MIN_FETCH_INTERVAL_HOURS,
    the run is skipped entirely. Protects the NewsAPI free-tier quota (100 req/day).
    11 locales × 1 request = 11 req/run; running twice daily stays well under the limit.
  - ON CONFLICT (id) DO NOTHING deduplicates by SHA-1 of (locale, title, published_at).

Requires: NEWSAPI_KEY environment variable. Exits cleanly (code 0) if key is absent.
"""

import hashlib
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

NEWSAPI_BASE = "https://newsapi.org/v2/everything"
REQUEST_TIMEOUT = 15
MAX_HEADLINES = 5               # per locale per run
LOOKBACK_DAYS = 14              # how far back to search for articles
MIN_FETCH_INTERVAL_HOURS = 6   # skip if we already fetched within this window

LOCALES = {
    "ar": {"query": "oro Argentina economía peso inflación",     "language": "es"},
    "br": {"query": "ouro Brasil economia real Selic",           "language": "pt"},
    "cl": {"query": "oro Chile economía cobre peso",             "language": "es"},
    "co": {"query": "oro Colombia economía peso minería",        "language": "es"},
    "cr": {"query": "oro Costa Rica economía colón inversión",   "language": "es"},
    "kz": {"query": "золото Казахстан экономика тенге",          "language": "ru"},
    "mx": {"query": "oro México economía peso Banxico",          "language": "es"},
    "pa": {"query": "oro Panamá inversión canal economía",       "language": "es"},
    "pe": {"query": "oro Perú economía minería sol",             "language": "es"},
    "uy": {"query": "oro Uruguay economía peso inversión",       "language": "es"},
    "en": {"query": "gold price economy Federal Reserve",        "language": "en"},
}


def last_fetch_age_hours(conn) -> float | None:
    """Return hours since the most recent insert, or None if table is empty."""
    cur = conn.cursor()
    cur.execute("SELECT MAX(created_at) FROM locale_data.news_headlines")
    last = cur.fetchone()[0]
    cur.close()

    if last is None:
        return None

    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)

    delta = datetime.now(timezone.utc) - last
    return delta.total_seconds() / 3600


def make_id(locale: str, title: str, published_at: str) -> str:
    raw = f"{locale}:{title}:{published_at}"
    return hashlib.sha1(raw.encode()).hexdigest()


def fetch_headlines(api_key: str, locale: str, query: str, language: str) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    params = {
        "q":        query,
        "language": language,
        "from":     cutoff,
        "sortBy":   "relevancy",
        "pageSize": MAX_HEADLINES,
        "apiKey":   api_key,
    }
    try:
        r = requests.get(NEWSAPI_BASE, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "ok":
            print(f"  [WARN] {locale.upper()}: NewsAPI — {data.get('message', 'unknown')}")
            return []
    except Exception as e:
        print(f"  [WARN] {locale.upper()}: request failed — {e}")
        return []

    articles = []
    for a in data.get("articles", [])[:MAX_HEADLINES]:
        title = (a.get("title") or "").strip()
        if not title or title == "[Removed]":
            continue
        pub = a.get("publishedAt", "")
        articles.append({
            "id":           make_id(locale, title, pub),
            "locale":       locale,
            "language":     language,
            "title":        title,
            "source":       (a.get("source") or {}).get("name"),
            "published_at": pub or None,
            "url":          a.get("url"),
        })
    return articles


def save_to_db(conn, records: list[dict]) -> int:
    cur = conn.cursor()
    inserted = 0

    for r in records:
        cur.execute(
            """
            INSERT INTO locale_data.news_headlines
                (id, locale, language, title, source, published_at, url)
            VALUES
                (%(id)s, %(locale)s, %(language)s, %(title)s, %(source)s, %(published_at)s, %(url)s)
            ON CONFLICT (id) DO NOTHING
            """,
            r,
        )
        inserted += cur.rowcount

    conn.commit()
    cur.close()
    return inserted


if __name__ == "__main__":
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        print("NEWSAPI_KEY not set — skipping locale news fetch (no error)")
        raise SystemExit(0)

    conn = psycopg2.connect(**DB_CONFIG)

    age_h = last_fetch_age_hours(conn)
    if age_h is not None and age_h < MIN_FETCH_INTERVAL_HOURS:
        print(f"Last fetch was {age_h:.1f}h ago (cooldown: {MIN_FETCH_INTERVAL_HOURS}h) — skipping")
        conn.close()
        raise SystemExit(0)

    last_str = f"{age_h:.1f}h ago" if age_h is not None else "never"
    print(f"Fetching locale news (last fetch: {last_str}, lookback: {LOOKBACK_DAYS}d, max {MAX_HEADLINES}/locale)...")

    all_records = []
    for locale, cfg in LOCALES.items():
        articles = fetch_headlines(api_key, locale, cfg["query"], cfg["language"])
        all_records.extend(articles)
        print(f"  {locale.upper()}: {len(articles)} articles fetched")

    inserted = save_to_db(conn, all_records)
    conn.close()

    dupes = len(all_records) - inserted
    print(f"\nInserted {inserted} new headlines into locale_data.news_headlines "
          f"({dupes} duplicate{'s' if dupes != 1 else ''} skipped)")
