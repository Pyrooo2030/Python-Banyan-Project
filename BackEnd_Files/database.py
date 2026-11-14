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

def list_auctions():
    with sqlite3.connect(DB_FILE) as db:
        rows = db.execute("""
            SELECT a.id, a.item_name,
                   COALESCE(MAX(b.amount), a.starting_price)
            FROM auctions AS a
            LEFT JOIN bids AS b ON b.auction_id = a.id
            GROUP BY a.id, a.item_name, a.starting_price
            ORDER BY a.id
        """).fetchall()

    if not rows:
        return "No items listed yet."

    return "\n".join(
        f"#{auction_id} | {name} | Current price: {price} pesos"
        for auction_id, name, price in rows
    )
def prepare_accounts():
    import secrets

    new_accounts = []

    with sqlite3.connect(DB_FILE) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                role TEXT NOT NULL CHECK (role IN ('seller', 'bidder', 'admin')),
                login_key TEXT NOT NULL
            )
        """)

        # Your existing auctions table already contains the practice mouse.
        columns = db.execute("PRAGMA table_info(auctions)").fetchall()
        if "seller" not in [column[1] for column in columns]:
            db.execute("ALTER TABLE auctions ADD COLUMN seller TEXT")

        for username, role in [
            ("seller1", "seller"),
            ("ana", "bidder"),
            ("admin1", "admin")
        ]:
            exists = db.execute(
                "SELECT 1 FROM users WHERE username = ?", (username,)
            ).fetchone()

            if exists is None:
                key = secrets.token_urlsafe(24)
                db.execute(
                    "INSERT INTO users VALUES (?, ?, ?)", (username, role, key)
                )
                new_accounts.append((username, role, key))

    for username, role, key in new_accounts:
        print(f"New demo account | {role} | {username} | login key: {key}")


def find_account(username):
    with sqlite3.connect(DB_FILE) as db:
        return db.execute(
            "SELECT role, login_key FROM users WHERE username = ?",
            (username,)
        ).fetchone()


def create_listing(seller, item_name, starting_price):
    with sqlite3.connect(DB_FILE) as db:
        cursor = db.execute("""
            INSERT INTO auctions (item_name, starting_price, seller)
            VALUES (?, ?, ?)
        """, (item_name, starting_price, seller))

        return f"Created auction #{cursor.lastrowid}: {item_name}."


def browse_items():
    with sqlite3.connect(DB_FILE) as db:
        rows = db.execute("""
            SELECT a.id, a.item_name, COALESCE(MAX(b.amount), a.starting_price)
            FROM auctions AS a
            LEFT JOIN bids AS b ON b.auction_id = a.id
            GROUP BY a.id, a.item_name, a.starting_price
            ORDER BY a.id
        """).fetchall()

    return "\n".join(
        f"#{number} | {name} | {price} pesos"
        for number, name, price in rows
    ) or "No listings yet."


def monitor_transactions():
    with sqlite3.connect(DB_FILE) as db:
        rows = db.execute("""
            SELECT b.id, b.auction_id, a.item_name, b.bidder, b.amount
            FROM bids AS b
            JOIN auctions AS a ON a.id = b.auction_id
            ORDER BY b.id DESC
            LIMIT 30
        """).fetchall()

    return "\n".join(
        f"Bid #{bid_id} | Auction #{auction_id} {name} | {bidder} | {amount} pesos"
        for bid_id, auction_id, name, bidder, amount in rows
    ) or "No accepted bids yet."