from python_banyan.banyan_base import BanyanBase


class AuctionServer(BanyanBase):
    def incoming_message_processing(self, topic, payload):
        print("Client sent:", payload)
        self.publish_payload({"message": "Server received your message"}, "auction.reply")


server = AuctionServer(back_plane_ip_address="10.215.206.48")
server.set_subscriber_topic("auction.request")
print("Auction server is waiting for a client...")
server.receive_loop()