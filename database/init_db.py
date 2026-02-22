import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "gold_analytics.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def init_db():
    with open(SCHEMA_PATH, "r") as f:
        schema = f.read()

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(schema)
    conn.commit()
    conn.close()

    print(f"Database initialized at: {DB_PATH}")


if __name__ == "__main__":
    init_db()
