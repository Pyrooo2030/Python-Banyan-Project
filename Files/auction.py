current_price = 100

for turn in range(2):
    bid = int(input("Enter your bid in whole pesos: "))

    if bid > current_price:
        current_price = bid
        print("Bid accepted.")
    else:
        print("Bid too low.")

    print("Current price:", current_price)