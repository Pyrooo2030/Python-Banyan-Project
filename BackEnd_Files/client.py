from python_banyan.banyan_base import BanyanBase


class AuctionClient(BanyanBase):
    def incoming_message_processing(self, topic, payload):
        print("Server replied:", payload["message"])


client = AuctionClient(back_plane_ip_address="10.215.206.48")
client.set_subscriber_topic("auction.reply")

bidder = input("Your name: ")
choice = input("1 = Browse items, 2 = Place a bid: ").strip()

if choice == "1":
    request = {"action": "list"}
elif choice == "2":
    try:
        auction_id = int(input("Auction number: "))
        bidder = input("Your name: ").strip()
        amount = int(input("Bid in whole pesos: "))
    except ValueError:
        print("Enter whole numbers for the auction number and bid.")
        raise SystemExit

    request = {
        "action": "bid",
        "auction_id": auction_id,
        "bidder": bidder,
        "amount": amount
    }
else:
    print("Choose 1 or 2.")
    raise SystemExit

client.publish_payload(request, "auction.request")
client.receive_loop()