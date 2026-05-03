import yfinance as yf
import psycopg2
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "gold_analytics"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}

# Fetch news from multiple gold-related tickers for wider coverage
TICKERS = ["GLD", "IAU", "GC=F", "XAUUSD=X"]


def fetch_news() -> list[dict]:
    seen_ids = set()
    records = []

    for ticker in TICKERS:
        try:
            articles = yf.Ticker(ticker).news or []
        except Exception as e:
            print(f"  Warning: failed to fetch news for {ticker}: {e}")
            continue

        for article in articles:
            content = article.get("content", {})
            article_id = content.get("id") or article.get("id")

            if not article_id or article_id in seen_ids:
                continue
            seen_ids.add(article_id)

            pub_date = content.get("pubDate") or content.get("displayTime")
            if not pub_date:
                continue

            title = content.get("title", "").strip()
            if not title:
                continue

            summary = (content.get("summary") or content.get("description") or "").strip()
            url = (content.get("canonicalUrl") or {}).get("url") or \
                  (content.get("clickThroughUrl") or {}).get("url")
            source = (content.get("provider") or {}).get("displayName")

            records.append({
                "id":           article_id,
                "published_at": pub_date,
                "title":        title,
                "summary":      summary or None,
                "url":          url,
                "source":       source,
                "ticker":       ticker,
            })

    return records


def save_to_db(records: list[dict]) -> int:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    inserted = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO news.articles (id, published_at, title, summary, url, source, ticker)
            VALUES (%(id)s, %(published_at)s, %(title)s, %(summary)s, %(url)s, %(source)s, %(ticker)s)
            ON CONFLICT (id) DO NOTHING
            """,
            r,
        )
        inserted += cur.rowcount

    conn.commit()
    cur.close()
    conn.close()
    return inserted


if __name__ == "__main__":
    print("Fetching gold news (yfinance)...")
    records = fetch_news()
    print(f"  Fetched {len(records)} unique articles across {len(TICKERS)} tickers")

    inserted = save_to_db(records)
    print(f"  Inserted {inserted} new articles into news.articles")

    print("\nLatest articles:")
    for r in sorted(records, key=lambda x: x["published_at"], reverse=True)[:5]:
        print(f"  [{r['published_at'][:10]}] {r['title'][:70]}")
