from python_banyan.banyan_base import BanyanBase


class AuctionClient(BanyanBase):
    def incoming_message_processing(self, topic, payload):
        print("Server replied:", payload["message"])


client = AuctionClient(back_plane_ip_address="10.215.206.48")
client.set_subscriber_topic("auction.reply")

input("Press Enter to send a test message...")
client.publish_payload({"message": "Hello from the bidder!"}, "auction.request")
client.receive_loop()