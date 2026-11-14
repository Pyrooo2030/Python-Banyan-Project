import sqlite3
from pathlib import Path


DB_FILE = Path(__file__).with_name("auction.db")


def prepare_database():
    with sqlite3.connect(DB_FILE) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS bids (
                id INTEGER PRIMARY KEY,
                auction_id INTEGER NOT NULL,
                bidder TEXT NOT NULL,
                amount INTEGER NOT NULL
            )
        """)


def place_bid(auction_id, bidder, amount):
    with sqlite3.connect(DB_FILE) as db:
        db.execute("BEGIN IMMEDIATE")

        row = db.execute(
            "SELECT MAX(amount) FROM bids WHERE auction_id = ?",
            (auction_id,)
        ).fetchone()

        current_price = row[0] if row[0] is not None else 100

        if amount <= current_price:
            return f"Bid too low. Current price is {current_price} pesos."

        db.execute(
            "INSERT INTO bids (auction_id, bidder, amount) VALUES (?, ?, ?)",
            (auction_id, bidder, amount)
        )
        return f"Accepted. {bidder} leads at {amount} pesos."