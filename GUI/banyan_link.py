import queue
import threading
import uuid

from python_banyan.banyan_base import BanyanBase
import messages as m


class BanyanLink(BanyanBase):
    def __init__(self, client_id):
        self.client_id = client_id
        self.token = None
        self.outbox = queue.Queue()
        self.inbox = queue.Queue()
        super().__init__(back_plane_ip_address=m.BACKPLANE_IP,
                         process_name=client_id,
                         receive_loop_idle_addition=self.send_pending)
        self.set_subscriber_topic(m.reply_topic(client_id))
        self.set_subscriber_topic(m.UPDATES)

    def send(self, payload):
        self.outbox.put(payload)

    def send_pending(self):
        while not self.outbox.empty():
            payload = self.outbox.get()
            payload.update(client_id=self.client_id,
                           reply_to=m.reply_topic(self.client_id),
                           token=self.token)
            self.publish_payload(payload, m.REQUESTS)

    def incoming_message_processing(self, topic, payload):
        if payload.get("type") == "login_reply" and payload.get("ok"):
            self.token = payload["data"]["token"]
        self.inbox.put((topic, payload))


def start_link():
    holder = {}
    ready = threading.Event()

    def run():
        holder["link"] = BanyanLink("gui-" + uuid.uuid4().hex[:6])
        ready.set()
        holder["link"].receive_loop()

    threading.Thread(target=run, daemon=True).start()
    ready.wait(5)
    return holder["link"]