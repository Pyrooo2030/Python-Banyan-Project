current_price = 100
highest_bidder = None


for bid_battle in range(2):
    bidder = input("Bidder name: ")
    bid = int(input("Enter your bid amount: "))

    if bid > current_price:
        current_price = bid
        highest_bidder = bidder
        print("Bid accepted.")
    else:
        print("Bid too low.")

    print("Current price:", current_price)

    if highest_bidder is None:
        print("Auction ended with no accepted bids.")
else:
    print("Winner:", highest_bidder)
    print("Winning bid:", current_price)