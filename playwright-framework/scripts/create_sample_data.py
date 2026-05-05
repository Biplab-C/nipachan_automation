"""
Run this script once to regenerate sample_data.xlsx and test.db in the data/ folder.
Usage:  python scripts/create_sample_data.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.excel_utils import ExcelUtils
from utils.db_utils import DatabaseUtils
from config.config import Config


def create_excel():
    excel_path = Config.DATA_DIR / "sample_data.xlsx"
    ExcelUtils.create_excel(
        excel_path,
        {
            "Users": [
                {"id": 1, "name": "Alice",   "email": "alice@example.com",   "age": 30, "role": "admin",   "city": "New York"},
                {"id": 2, "name": "Bob",     "email": "bob@example.com",     "age": 25, "role": "user",    "city": "Los Angeles"},
                {"id": 3, "name": "Charlie", "email": "charlie@example.com", "age": 35, "role": "manager", "city": "Chicago"},
                {"id": 4, "name": "Diana",   "email": "diana@example.com",   "age": 28, "role": "user",    "city": "New York"},
                {"id": 5, "name": "Eve",     "email": "eve@example.com",     "age": 32, "role": "admin",   "city": "Boston"},
            ],
            "Products": [
                {"id": 101, "name": "Laptop",  "price": 999.99, "category": "Electronics", "stock": 50},
                {"id": 102, "name": "Mouse",   "price":  29.99, "category": "Electronics", "stock": 200},
                {"id": 103, "name": "Desk",    "price": 349.99, "category": "Furniture",   "stock": 30},
                {"id": 104, "name": "Chair",   "price": 199.99, "category": "Furniture",   "stock": 45},
                {"id": 105, "name": "Monitor", "price": 499.99, "category": "Electronics", "stock": 75},
            ],
        },
    )
    print(f"[OK] Excel created: {excel_path}")


def create_sqlite_db():
    db = DatabaseUtils()

    db.create_table("""
        CREATE TABLE IF NOT EXISTS users (
            id      INTEGER PRIMARY KEY,
            name    TEXT NOT NULL,
            email   TEXT UNIQUE NOT NULL,
            age     INTEGER,
            role    TEXT,
            city    TEXT
        )
    """)

    db.create_table("""
        CREATE TABLE IF NOT EXISTS products (
            id       INTEGER PRIMARY KEY,
            name     TEXT NOT NULL,
            price    REAL,
            category TEXT,
            stock    INTEGER
        )
    """)

    # Seed users only if table is empty
    if db.row_count("users") == 0:
        db.insert_many("users", [
            {"id": 1, "name": "Alice",   "email": "alice@example.com",   "age": 30, "role": "admin",   "city": "New York"},
            {"id": 2, "name": "Bob",     "email": "bob@example.com",     "age": 25, "role": "user",    "city": "Los Angeles"},
            {"id": 3, "name": "Charlie", "email": "charlie@example.com", "age": 35, "role": "manager", "city": "Chicago"},
        ])

    if db.row_count("products") == 0:
        db.insert_many("products", [
            {"id": 101, "name": "Laptop",  "price": 999.99, "category": "Electronics", "stock": 50},
            {"id": 102, "name": "Mouse",   "price":  29.99, "category": "Electronics", "stock": 200},
        ])

    db.close()
    print(f"[OK] SQLite DB created: {Config.DB_URL}")


if __name__ == "__main__":
    Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    create_excel()
    create_sqlite_db()
    print("\nSample data generation complete.")
