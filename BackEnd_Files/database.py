import secrets
import sqlite3
import time
from pathlib import Path


DB_FILE = Path(__file__).with_name("auction.db")
AUCTION_SECONDS = 60


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


def prepare_accounts():
    new_accounts = []

    with sqlite3.connect(DB_FILE) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                role TEXT NOT NULL CHECK (role IN ('seller', 'bidder', 'admin')),
                login_key TEXT NOT NULL
            )
        """)

        columns = {row[1] for row in db.execute("PRAGMA table_info(auctions)")}
        if "seller" not in columns:
            db.execute("ALTER TABLE auctions ADD COLUMN seller TEXT")

        for username, role in [
            ("seller1", "seller"),
            ("seller2", "seller"),
            ("ana", "bidder"),
            ("admin1", "admin"),
        ]:
            existing = db.execute(
                "SELECT 1 FROM users WHERE username = ?", (username,)
            ).fetchone()

            if existing is None:
                key = secrets.token_urlsafe(24)
                db.execute("""
                    INSERT INTO users (username, role, login_key)
                    VALUES (?, ?, ?)
                """, (username, role, key))
                new_accounts.append((username, role, key))

    for username, role, key in new_accounts:
        print(f"New demo account | {role} | {username} | login key: {key}")


def find_account(username):
    with sqlite3.connect(DB_FILE) as db:
        return db.execute(
            "SELECT role, login_key FROM users WHERE username = ?", (username,)
        ).fetchone()


def prepare_closing():
    with sqlite3.connect(DB_FILE) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(auctions)")}

        if "closes_at" not in columns:
            db.execute("ALTER TABLE auctions ADD COLUMN closes_at INTEGER")
        if "closed" not in columns:
            db.execute("ALTER TABLE auctions ADD COLUMN closed INTEGER DEFAULT 0")
        if "winner" not in columns:
            db.execute("ALTER TABLE auctions ADD COLUMN winner TEXT")
        if "winning_amount" not in columns:
            db.execute("ALTER TABLE auctions ADD COLUMN winning_amount INTEGER")


def create_listing(seller, item_name, starting_price):
    closes_at = int(time.time()) + AUCTION_SECONDS

    with sqlite3.connect(DB_FILE) as db:
        cursor = db.execute("""
            INSERT INTO auctions (item_name, starting_price, seller, closes_at)
            VALUES (?, ?, ?, ?)
        """, (item_name, starting_price, seller, closes_at))
        auction_id = cursor.lastrowid

    return {
        "event": "listed",
        "auction_id": auction_id,
        "item_name": item_name,
        "seller": seller,
        "amount": starting_price,
        "closes_at": closes_at,
        "message": (
            f"Created auction #{auction_id}: {item_name} | "
            f"Seller: {seller} | {starting_price} pesos | {AUCTION_SECONDS}s left"
        ),
    }


def place_bid(auction_id, bidder, amount):
    with sqlite3.connect(DB_FILE) as db:
        db.execute("BEGIN IMMEDIATE")

        auction = db.execute("""
            SELECT item_name, starting_price, seller, closed, closes_at
            FROM auctions
            WHERE id = ?
        """, (auction_id,)).fetchone()

        if auction is None:
            return "Auction not found."

        item_name, starting_price, seller, closed, closes_at = auction

        if seller == bidder:
            return "Denied. You cannot bid on your own listing."

        now = time.time()
        if closed or (closes_at is not None and now >= closes_at):
            return "Bid rejected. This auction has ended."

        highest_bid = db.execute(
            "SELECT MAX(amount) FROM bids WHERE auction_id = ?", (auction_id,)
        ).fetchone()[0]

        current_price = starting_price if highest_bid is None else highest_bid

        if amount <= current_price:
            return {
                "accepted": False,
                "message": f"Bid too low. Current price is {current_price} pesos.",
            }

        new_deadline = int(now) + AUCTION_SECONDS

        db.execute("""
            INSERT INTO bids (auction_id, bidder, amount)
            VALUES (?, ?, ?)
        """, (auction_id, bidder, amount))

        db.execute(
            "UPDATE auctions SET closes_at = ? WHERE id = ?",
            (new_deadline, auction_id),
        )

    return {
        "accepted": True,
        "auction_id": auction_id,
        "bidder": bidder,
        "amount": amount,
        "closes_at": new_deadline,
        "message": (
            f"Accepted. {bidder} leads on {item_name} at {amount} pesos. "
            f"Timer reset to {AUCTION_SECONDS} seconds."
        ),
    }


def browse_items():
    now = int(time.time())

    with sqlite3.connect(DB_FILE) as db:
        rows = db.execute("""
            SELECT a.id, a.item_name, a.seller, a.closes_at,
                   a.starting_price, b.amount, b.bidder
            FROM auctions AS a
            LEFT JOIN bids AS b ON b.id = (
                SELECT id FROM bids
                WHERE auction_id = a.id
                ORDER BY amount DESC, id ASC
                LIMIT 1
            )
            WHERE a.closed = 0
              AND (a.closes_at IS NULL OR a.closes_at > ?)
            ORDER BY a.closes_at IS NULL, a.closes_at, a.id
        """, (now,)).fetchall()

    auctions = []
    lines = []

    for auction_id, name, seller, deadline, starting_price, top_bid, leader in rows:
        current_price = starting_price if top_bid is None else top_bid

        auctions.append({
            "auction_id": auction_id,
            "item_name": name,
            "seller": seller,
            "starting_price": starting_price,
            "current_price": current_price,
            "has_bids": top_bid is not None,
            "next_minimum": current_price + 1,
            "closes_at": deadline,
            "leader": leader,
        })

        remaining = "No deadline" if deadline is None else f"{deadline - now}s left"
        lines.append(
            f"#{auction_id} {name} | Seller: {seller or 'Unassigned'} | "
            f"{current_price} pesos | Leader: {leader or 'No bids yet'} | {remaining}"
        )

    return {
        "message": "\n".join(lines) or "No auctions are open right now.",
        "auctions": auctions,
        "server_time": now,
    }


def list_auctions():
    return browse_items()


def monitor_transactions():
    with sqlite3.connect(DB_FILE) as db:
        rows = db.execute("""
            SELECT b.id, a.id, a.item_name, a.seller, b.bidder, b.amount,
                   a.closed, a.winner, a.winning_amount
            FROM bids AS b
            JOIN auctions AS a ON a.id = b.auction_id
            ORDER BY b.id DESC
        """).fetchall()

    if not rows:
        return "No accepted bids have been recorded."

    lines = ["ADMIN | All accepted bids, newest first"]
    for bid_id, number, name, seller, bidder, amount, closed, winner, final_price in rows:
        status = f"Closed | Winner: {winner} at {final_price} pesos" if closed else "Open"
        lines.append(
            f"Bid #{bid_id} | Auction #{number} {name} | "
            f"Seller: {seller or 'Unassigned'} | {bidder} bid {amount} pesos | {status}"
        )

    return "\n".join(lines)


def close_due_auctions():
    events = []

    with sqlite3.connect(DB_FILE) as db:
        db.execute("BEGIN IMMEDIATE")
        due = db.execute("""
            SELECT id, item_name FROM auctions
            WHERE closed = 0 AND closes_at <= ?
            ORDER BY closes_at, id
        """, (int(time.time()),)).fetchall()

        for auction_id, item_name in due:
            top_bid = db.execute("""
                SELECT bidder, amount FROM bids
                WHERE auction_id = ?
                ORDER BY amount DESC, id ASC
                LIMIT 1
            """, (auction_id,)).fetchone()

            winner, amount = top_bid if top_bid else (None, None)

            db.execute("""
                UPDATE auctions
                SET closed = 1, winner = ?, winning_amount = ?
                WHERE id = ?
            """, (winner, amount, auction_id))

            if winner is None:
                message = f"Auction #{auction_id} {item_name} closed with no bids."
            else:
                message = f"Auction #{auction_id} {item_name} closed. {winner} won at {amount} pesos."

            events.append({
                "event": "closed",
                "auction_id": auction_id,
                "winner": winner,
                "amount": amount,
                "message": message,
            })

    return events


def all_results():
    with sqlite3.connect(DB_FILE) as db:
        rows = db.execute("""
            SELECT id, item_name, winner, winning_amount
            FROM auctions
            WHERE closed = 1
            ORDER BY closes_at DESC, id DESC
        """).fetchall()

    if not rows:
        return "No auctions have finished yet."

    lines = ["AUCTION RESULTS | Most recently closed first"]
    for number, name, winner, amount in rows:
        if winner is None:
            lines.append(f"#{number} {name} | No winner (no bids)")
        else:
            lines.append(f"#{number} {name} | Winner: {winner} | {amount} pesos")

    return "\n".join(lines)


def auction_result(auction_id):
    with sqlite3.connect(DB_FILE) as db:
        row = db.execute("""
            SELECT item_name, closes_at, closed, winner, winning_amount
            FROM auctions
            WHERE id = ?
        """, (auction_id,)).fetchone()

    if row is None:
        return "Auction not found."

    name, deadline, closed, winner, amount = row

    if closed:
        if winner is None:
            return f"{name} closed with no accepted bids."
        return f"{name} closed. Winner: {winner} at {amount} pesos."

    if deadline is None:
        return f"{name} is open. No deadline was set."

    remaining = deadline - int(time.time())
    if remaining <= 0:
        return f"Bidding has ended for {name}. The server is recording the result."

    return f"{name} is open. {remaining} seconds remaining."