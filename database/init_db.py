import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "127.0.0.1"),
    "port":     os.getenv("DB_PORT", "5432"),
    "dbname":   os.getenv("DB_NAME", "gold_analytics"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}

BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent


def discover_schemas() -> list[Path]:
    """
    Return schema files in a stable, deterministic order:
      1. database/schema.sql  (base — always first)
      2. data_sources/*/schema.sql  (one per data source, sorted alphabetically)
    New data sources are picked up automatically — no manual list to maintain.
    """
    base_schema = BASE_DIR / "schema.sql"
    source_schemas = sorted((ROOT_DIR / "data_sources").rglob("schema.sql"))
    return [base_schema] + source_schemas


def init_db():
    schema_files = discover_schemas()
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    applied = skipped = 0
    for path in schema_files:
        sql = path.read_text(encoding="utf-8")
        # Skip files that contain no executable SQL (comments + whitespace only)
        has_sql = any(
            line.strip() and not line.strip().startswith("--")
            for line in sql.splitlines()
        )
        if not has_sql:
            print(f"  Skipped (empty): {path.relative_to(ROOT_DIR)}")
            skipped += 1
            continue
        cur.execute(sql)
        print(f"  Applied: {path.relative_to(ROOT_DIR)}")
        applied += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone — {applied} applied, {skipped} skipped  ({DB_CONFIG['dbname']} on {DB_CONFIG['host']})")


if __name__ == "__main__":
    init_db()
