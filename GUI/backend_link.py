import hashlib
import hmac
import json
import queue
import threading
import time
import uuid

from python_banyan.banyan_base import BanyanBase

import messages as m


class BackendLink(BanyanBase):
    def __init__(self, backplane_ip):
        self.outbox = queue.Queue()
        self.inbox = queue.Queue()
        self.username = None
        self.key = None
        self.pending = {}
        self.items = {}
        self.offset = 0.0
        self.events_on = False
        super().__init__(back_plane_ip_address=backplane_ip)
        self.receive_loop_idle_addition = self.send_pending

    def send(self, payload):
        self.outbox.put(payload)

    def reply(self, gui_type, ok, data=None, error=None):
        self.inbox.put(("reply", {"type": gui_type + "_reply", "ok": ok,
                                  "data": data, "error": error}))

    def send_pending(self):
        while not self.outbox.empty():
            self.dispatch(self.outbox.get())

    def dispatch(self, p):
        kind = p["type"]
        if kind == m.LOGIN:
            self.username = (p.get("username") or "").strip()
            self.key = (p.get("password") or "").strip()
            self.call("login", {}, kind)
        elif kind == m.REGISTER:
            self.reply(kind, False, error="Accounts are created on the server. "
                                          "Ask the admin for a login key.")
        elif not self.username:
            return
        elif kind == m.LIST_ITEMS:
            self.call("Browse", {}, kind)
        elif kind == m.PLACE_BID:
            self.call("bid", {"auction_id": int(p["item_id"]),
                              "amount": int(round(p["amount"]))}, kind)
        elif kind == m.CREATE_LISTING:
            self.call("list_item", {"name": p["title"],
                                    "price": int(round(p["starting_price"]))}, kind)
        elif kind == m.TRANSACTIONS:
            self.call("monitor", {}, kind)
        elif kind == m.RESULTS:
            self.call("result", {}, kind)

    def call(self, action, data, gui_type):
        request = {"id": uuid.uuid4().hex, "time": int(time.time()),
                   "username": self.username, "action": action, "data": data}
        raw = json.dumps(request, sort_keys=True).encode()
        signature = hmac.new(self.key.encode(), raw, hashlib.sha256).hexdigest()

        topic = "auction.reply." + request["id"]
        self.pending[topic] = gui_type
        self.set_subscriber_topic(topic)
        time.sleep(0.2)
        self.publish_payload({"request": request, "signature": signature}, "auction.request")

    def incoming_message_processing(self, topic, payload):
        if topic == "auction.events":
            self.handle_event(payload)
            return
        gui_type = self.pending.pop(topic, None)
        if gui_type is not None:
            self.handle_reply(gui_type, payload)

    def local_time(self, server_epoch):
        return None if server_epoch is None else server_epoch - self.offset

    def to_item(self, a):
        return {"id": a["auction_id"], "title": a["item_name"], "description": "",
                "starting_price": a["starting_price"], "min_increment": 1,
                "status": "open",
                "current_price": a["current_price"] if a["has_bids"] else None,
                "next_minimum": a["next_minimum"],
                "seller_name": a["seller"], "winner_name": a["leader"],
                "end_time": self.local_time(a["closes_at"])}

    def handle_reply(self, gui_type, r):
        msg = r.get("message", "")
        if gui_type == m.LOGIN:
            if "role" in r and "username" in r:
                if not self.events_on:
                    self.set_subscriber_topic("auction.events")
                    self.events_on = True
                user = {"id": 0, "username": r["username"], "role": r["role"]}
                self.reply(gui_type, True, {"token": "", "user": user})
            else:
                self.reply(gui_type, False, error=msg)
        elif gui_type == m.LIST_ITEMS:
            if "auctions" in r:
                self.offset = r.get("server_time", time.time()) - time.time()
                items = [self.to_item(a) for a in r["auctions"]]
                for item in items:
                    self.items[item["id"]] = item
                self.reply(gui_type, True, items)
            else:
                self.reply(gui_type, False, error=msg)
        elif gui_type == m.PLACE_BID:
            if r.get("accepted"):
                self.reply(gui_type, True, self.apply_bid(r))
            else:
                self.reply(gui_type, False, error=msg)
        elif gui_type == m.CREATE_LISTING:
            if r.get("event") == "listed":
                self.reply(gui_type, True, self.apply_listed(r))
            else:
                self.reply(gui_type, False, error=msg)
        else:
            self.reply(gui_type, True, msg)

    def blank(self, auction_id):
        return {"id": auction_id, "title": f"Auction #{auction_id}", "description": "",
                "starting_price": 0, "min_increment": 1, "status": "open",
                "current_price": None, "next_minimum": 1, "seller_name": None,
                "winner_name": None, "end_time": None}

    def apply_bid(self, e):
        item = dict(self.items.get(e["auction_id"]) or self.blank(e["auction_id"]))
        item.update(status="open", current_price=e["amount"], next_minimum=e["amount"] + 1,
                    winner_name=e["bidder"], end_time=self.local_time(e["closes_at"]))
        self.items[item["id"]] = item
        return item

    def apply_listed(self, e):
        item = self.blank(e["auction_id"])
        item.update(title=e["item_name"], starting_price=e["amount"],
                    next_minimum=e["amount"] + 1, seller_name=e["seller"],
                    end_time=self.local_time(e["closes_at"]))
        self.items[item["id"]] = item
        return item

    def apply_closed(self, e):
        item = dict(self.items.get(e["auction_id"]) or self.blank(e["auction_id"]))
        item.update(status="closed", winner_name=e.get("winner"), current_price=e.get("amount"))
        self.items[item["id"]] = item
        return item

    def handle_event(self, e):
        kind = e.get("event")
        if kind == "bid_accepted":
            previous_item = self.items.get(e["auction_id"], {})
            previous_leader = previous_item.get("winner_name")

            out = {
                "type": "bid_accepted",
                "item": self.apply_bid(e),
                "previous_leader": previous_leader,
            }
        elif kind == "listed":
            out = {"type": "auction_opened", "item": self.apply_listed(e)}
        elif kind == "closed":
            out = {"type": "auction_closed", "item": self.apply_closed(e)}
        else:
            return
        self.inbox.put(("events", out))


def start_link():
    link = BackendLink(m.BACKPLANE_IP)
    threading.Thread(target=link.receive_loop, daemon=True).start()
    return link