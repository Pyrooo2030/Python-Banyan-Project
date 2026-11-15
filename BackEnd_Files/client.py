import getpass
import hashlib
import hmac
import json
import time
import uuid


from python_banyan.banyan_base import BanyanBase
from queue import Queue, Empty
from threading import Thread


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
        if topic == "auction.events":
            print(f"\n[LIVE] {payload['message']}", flush=True)
            return
        if topic != self.reply_topic:
            return

        message = payload["message"]
        print("\n" + message)

        if self.last_action == "login" and not message.startswith("Now Logged in as "):
            raise SystemExit

    
        if self.last_action == "login":
            self.set_subscriber_topic("auction.events")

        Thread(target=self.show_menu, daemon=True).start()

    def show_menu(self):
        while True:
            print("\n1 Browse | 2 Create listing | 3 Bid | 4 Monitor | 5 Results | 0 Exit")
            choice = input("Choose: ").strip()

            try:
                if choice == "0":
                    self.queue_request("exit", {})
                    return
                if choice == "1":
                    self.queue_request("Browse", {})
                elif choice == "2":
                    name = input("Item name: ")
                    price = int(input("Starting price in pesos: "))
                    self.queue_request("list_item", {"name": name, "price": price})
                elif choice == "3":
                    number = int(input("Auction number: "))
                    amount = int(input("Bid in pesos: "))
                    self.queue_request("bid", {"auction_id": number, "amount": amount})
                elif choice == "4":
                    self.queue_request("monitor", {})
                elif choice == "5":
                    number = int(input("Auction number: "))
                    self.queue_request("result", {"auction_id": number})
                else:
                    print("Choose a number from 0 to 5.")
                    continue
            except ValueError:
                print("Enter a whole number.")
                continue

            return  # Wait for the server's reply before showing the menu again.
    def queue_request(self, action, data):
        self.menu_requests.put((action, data))

    def process_menu_queue(self):
        try:
            action, data = self.menu_requests.get_nowait()
        except Empty:
            return

        if action == "exit":
            raise SystemExit

        self.send_request(action, data)

backplane_ip = input("Backplane IP: ").strip()
client = AuctionClient(back_plane_ip_address=backplane_ip)
client.menu_requests = Queue()
client.receive_loop_idle_addition = client.process_menu_queue
client.username = input("Username: ").strip()
client.key = input("Login key: ").strip()
client.send_request("login", {})
client.receive_loop()