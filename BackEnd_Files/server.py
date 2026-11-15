import hashlib
import hmac
import json
import time

from database import auction_result
from python_banyan.banyan_base import BanyanBase
from threading import Thread
from database import prepare_closing, close_due_auctions
from database import (
    prepare_database, prepare_accounts, find_account,
    create_listing, browse_items, place_bid, monitor_transactions
)


def handle_action(username, role, action, data):
    if action == "login":
        return f"Now Logged in as {username} ({role})."

    if action == "Browse":
        return browse_items()

    if action == "list_item":
        if role != "seller":
            return "Denied. Only sellers can create listings."

        name = data.get("name")
        price = data.get("price")
        if not isinstance(name, str) or not name.strip():
            return "Enter an item name."
        if type(price) is not int or not 0 <= price <= 2_147_483_647:
            return "Enter a valid starting price."

        return create_listing(username, name.strip(), price)

    if action == "bid":
        if role != "bidder":
            return "Denied. Only bidders can place bids."

        number = data.get("auction_id")
        amount = data.get("amount")
        if any(type(n) is not int or not 1 <= n <= 2_147_483_647
               for n in (number, amount)):
            return "Enter a positive auction number and whole-peso bid."

        result = place_bid(number, username, amount)
        # Supports either version of place_bid from our earlier steps.
        return result

    if action == "monitor":
        if role != "admin":
            return "Denied. Only admins can monitor transactions."
        return monitor_transactions()

    if action == "result":
        number = data.get("auction_id")
        if type(number) is not int or not 1 <= number <= 2_147_483_647:
            return "Enter a valid auction number."
        return auction_result(number)

    return "Unknown action."


class AuctionServer(BanyanBase):
    def incoming_message_processing(self, topic, payload):
        if not isinstance(payload, dict):
            return

        request = payload.get("request")
        signature = payload.get("signature")
        if not isinstance(request, dict) or not isinstance(signature, str):
            return

        request_id = request.get("id")
        if not isinstance(request_id, str) or len(request_id) != 32:
            return
        if any(c not in "0123456789abcdef" for c in request_id):
            return

        message = "Login failed. Check your username and login key."
        username = request.get("username")
        account = find_account(username) if isinstance(username, str) else None
        now = int(time.time())

        if account:
            role, key = account
            raw = json.dumps(request, sort_keys=True).encode()
            expected = hmac.new(key.encode(), raw, hashlib.sha256).hexdigest()
            timestamp = request.get("time")

            if hmac.compare_digest(expected, signature.encode().hex()
                                   if not signature.isascii() else signature):
                if type(timestamp) is not int or abs(now - timestamp) > 60:
                    message = "Request expired. Check both computers' clocks."
                elif request_id in self.recent_requests:
                    return
                elif isinstance(request.get("data"), dict):
                    self.recent_requests = {
                        rid: expiry for rid, expiry in self.recent_requests.items()
                        if expiry >= now
                    }
                    self.recent_requests[request_id] = timestamp + 60
                    message = handle_action(
                        username, role, request.get("action"), request["data"]
                    )

        if isinstance(message, dict):
            if message.get("accepted"):
                self.publish_payload(
                    {"event": "bid_accepted", **message},
                    "auction.events"
                )
            message = message["message"]

        self.publish_payload({"message": message}, "auction.reply." + request_id)
prepare_database()
prepare_accounts()
prepare_closing()

backplane_ip = input("Backplane IP: ").strip()
server = AuctionServer(back_plane_ip_address=backplane_ip)
server.recent_requests = {}
server.set_subscriber_topic("auction.request")

next_deadline_check = 0.0


def check_deadlines():
    global next_deadline_check

    now = time.monotonic()
    if now < next_deadline_check:
        return

    next_deadline_check = now + 1
    for event in close_due_auctions():
        server.publish_payload(event, "auction.events")


server.receive_loop_idle_addition = check_deadlines
print("Auction server ready.")
server.receive_loop()