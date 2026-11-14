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
        db.execute("""
            CREATE TABLE IF NOT EXISTS auctions (
                id INTEGER PRIMARY KEY,
                item_name TEXT NOT NULL,
                starting_price INTEGER NOT NULL CHECK (starting_price >= 0)
            )
        """)

        db.execute("""
            INSERT OR IGNORE INTO auctions (id, item_name, starting_price)
            VALUES (1, 'Wireless Mouse', 100)
        """)


def place_bid(auction_id, bidder, amount):
    with sqlite3.connect(DB_FILE) as db:
        db.execute("BEGIN IMMEDIATE")

        row = db.execute(
            "SELECT MAX(amount) FROM bids WHERE auction_id = ?",
            (auction_id,)
        ).fetchone()

        listing = db.execute(
            "SELECT item_name, starting_price FROM auctions WHERE id = ?",
            (auction_id,)
        ).fetchone()

        if listing is None:
            return "Auction not found."

        item_name, starting_price = listing
        current_price = row[0] if row[0] is not None else starting_price

        if amount <= current_price:
            return f"Bid too low. Current price is {current_price} pesos."

        db.execute(
            "INSERT INTO bids (auction_id, bidder, amount) VALUES (?, ?, ?)",
            (auction_id, bidder, amount)
        )
        return f"Accepted. {bidder} leads on {item_name} at {amount} pesos."