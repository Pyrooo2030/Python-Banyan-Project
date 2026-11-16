import hashlib
import hmac
import json
import time

from python_banyan.banyan_base import BanyanBase

from database import (
    all_results,
    browse_items,
    close_due_auctions,
    create_listing,
    find_account,
    monitor_transactions,
    place_bid,
    prepare_accounts,
    prepare_closing,
    prepare_database,
)


def handle_action(username, role, action, data):
    if action == "login":
        return {
            "message": f"Now Logged in as {username} ({role}).",
            "username": username,
            "role": role,
        }

    if action == "Browse":
        result = browse_items()
        for auction in result["auctions"]:
            auction["can_bid"] = (
                role in ("bidder", "seller")
                and auction["seller"] != username
            )
        return result

    if action == "list_item":
        if role != "seller":
            return "Denied. Only sellers can create listings."

        name = data.get("name")
        price = data.get("price")

        if not isinstance(name, str) or not name.strip():
            return "Enter an item name."
        if type(price) is not int or not 0 <= price <= 2_147_483_647:
            return "Enter a valid whole-peso starting price."

        return create_listing(username, name.strip(), price)

    if action == "bid":
        if role not in ("bidder", "seller"):
            return "Denied. Only bidders and sellers can place bids."

        auction_id = data.get("auction_id")
        amount = data.get("amount")

        for value in (auction_id, amount):
            if type(value) is not int or not 1 <= value <= 2_147_483_647:
                return "Enter a positive auction number and whole-peso bid."

        # place_bid checks the listing's owner, deadline, and current price.
        return place_bid(auction_id, username, amount)

    if action == "monitor":
        if role != "admin":
            return "Denied. Only admins can monitor transactions."
        return monitor_transactions()

    if action == "result":
        return all_results()

    return "Unknown action."


class AuctionServer(BanyanBase):
    def __init__(self, backplane_ip):
        super().__init__(back_plane_ip_address=backplane_ip)
        self.recent_requests = {}
        self.next_deadline_check = 0.0
        self.receive_loop_idle_addition = self.check_deadlines
        self.set_subscriber_topic("auction.request")

    def check_deadlines(self):
        now = time.monotonic()
        if now < self.next_deadline_check:
            return

        self.next_deadline_check = now + 1
        for event in close_due_auctions():
            self.publish_payload(event, "auction.events")

    def incoming_message_processing(self, topic, payload):
        if topic != "auction.request" or not isinstance(payload, dict):
            return

        request = payload.get("request")
        signature = payload.get("signature")
        if not isinstance(request, dict) or not isinstance(signature, str):
            return

        request_id = request.get("id")
        if not isinstance(request_id, str) or len(request_id) != 32:
            return
        if any(char not in "0123456789abcdef" for char in request_id):
            return

        # Also check while clients are active so deadlines get processed
        # even when requests keep arriving.
        self.check_deadlines()

        reply_topic = "auction.reply." + request_id
        username = request.get("username")
        account = find_account(username) if isinstance(username, str) else None

        if account is None:
            self.publish_payload(
                {"message": "Login failed. Check your username and login key."},
                reply_topic,
            )
            return

        role, key = account
        raw = json.dumps(request, sort_keys=True).encode()
        expected = hmac.new(key.encode(), raw, hashlib.sha256).hexdigest()

        if not signature.isascii() or not hmac.compare_digest(expected, signature):
            self.publish_payload(
                {"message": "Login failed. Check your username and login key."},
                reply_topic,
            )
            return

        now = int(time.time())
        timestamp = request.get("time")
        if type(timestamp) is not int or abs(now - timestamp) > 60:
            self.publish_payload(
                {"message": "Request expired. Check both computers' clocks."},
                reply_topic,
            )
            return

        data = request.get("data")
        if not isinstance(data, dict):
            self.publish_payload({"message": "Invalid request data."}, reply_topic)
            return

        self.recent_requests = {
            rid: expires
            for rid, expires in self.recent_requests.items()
            if expires >= now
        }
        if request_id in self.recent_requests:
            return
        self.recent_requests[request_id] = timestamp + 60

        result = handle_action(username, role, request.get("action"), data)
        reply = result if isinstance(result, dict) else {"message": result}

        if reply.get("accepted"):
            self.publish_payload(
                {**reply, "event": "bid_accepted"}, "auction.events"
            )
        elif reply.get("event") == "listed":
            self.publish_payload(reply, "auction.events")

        self.publish_payload(reply, reply_topic)


if __name__ == "__main__":
    prepare_database()
    prepare_accounts()
    prepare_closing()

    backplane_ip = input("Backplane IP: ").strip()
    server = AuctionServer(backplane_ip)
    print("Auction server ready.")
    server.receive_loop()