BACKPLANE_IP = None

REQUESTS = "auction.requests"
UPDATES = "auction.updates"

def reply_topic(client_id):
    return f"auction.reply.{client_id}"

REGISTER = "register"
LOGIN = "login"
LIST_ITEMS = "list_items"
PLACE_BID = "place_bid"
CREATE_LISTING = "create_listing"
PENDING_LISTINGS = "pending_listings"
APPROVE_LISTING = "approve_listing"
REJECT_LISTING = "reject_listing"
TRANSACTIONS = "transactions"