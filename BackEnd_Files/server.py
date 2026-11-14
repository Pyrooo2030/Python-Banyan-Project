from python_banyan.banyan_base import BanyanBase
from database import prepare_database, place_bid


class AuctionServer(BanyanBase):
     def incoming_message_processing(self, topic, payload):
        message = place_bid(1, payload["bidder"], payload["amount"])
        print(message)
        self.publish_payload({"message": message}, "auction.reply")

prepare_database()
server = AuctionServer(back_plane_ip_address="10.215.206.48")
server.set_subscriber_topic("auction.request")
print("Auction server is ready. Waiting for bids...")
server.receive_loop()