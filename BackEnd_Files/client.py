import getpass
import hashlib
import hmac
import json
import time
import uuid

from python_banyan.banyan_base import BanyanBase


class AuctionClient(BanyanBase):
    def send_request(self, action, data):
        request = {
            "id": uuid.uuid4().hex,
            "time": int(time.time()),
            "username": self.username,
            "action": action,
            "data": data
        }
        raw = json.dumps(request, sort_keys=True).encode()
        signature = hmac.new(self.key.encode(), raw, hashlib.sha256).hexdigest()

        self.reply_topic = "auction.reply." + request["id"]
        self.set_subscriber_topic(self.reply_topic)
        time.sleep(0.2)
        self.last_action = action
        self.publish_payload(
            {"request": request, "signature": signature}, "auction.request"
        )

    def incoming_message_processing(self, topic, payload):
        if topic != self.reply_topic:
            return

        message = payload["message"]
        print("\n" + message)

        if self.last_action == "login" and not message.startswith("Now Logged in as "):
            raise SystemExit

        self.show_menu()

    def show_menu(self):
        while True:
            print("\n1 Browse | 2 Create listing | 3 Bid | 4 Monitor | 0 Exit")
            choice = input("Choose: ").strip()

            try:
                if choice == "0":
                    raise SystemExit
                if choice == "1":
                    self.send_request("browse", {})
                elif choice == "2":
                    name = input("Item name: ")
                    price = int(input("Starting price in pesos: "))
                    self.send_request("list_item", {"name": name, "price": price})
                elif choice == "3":
                    number = int(input("Auction number: "))
                    amount = int(input("Bid in pesos: "))
                    self.send_request("bid", {"auction_id": number, "amount": amount})
                elif choice == "4":
                    self.send_request("monitor", {})
                else:
                    print("Choose a number from 0 to 4.")
                    continue
            except ValueError:
                print("Enter a whole number.")
                continue

            return  # Wait for the server's reply before showing the menu again.


client = AuctionClient(back_plane_ip_address="10.215.206.48")
client.username = input("Username: ").strip()
client.key = input("Login key: ").strip()
client.send_request("login", {})
client.receive_loop()