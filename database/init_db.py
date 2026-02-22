import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "gold_analytics"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def init_db():
    with open(SCHEMA_PATH, "r") as f:
        schema = f.read()

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(schema)
    conn.commit()
    cur.close()
    conn.close()

    print(f"Database initialized: {DB_CONFIG['dbname']} on {DB_CONFIG['host']}")


if __name__ == "__main__":
    init_db()
