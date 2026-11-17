import time
from datetime import datetime, timezone

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QAbstractItemView, QDoubleSpinBox, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

import messages as m

FMT = "%Y-%m-%d %H:%M:%S"
COLUMNS = ["ID", "Item", "Current price", "Next minimum", "Time left", "Leader"]


def time_left(end_time):
    if end_time is None or end_time == "":
        return "-"
    if isinstance(end_time, (int, float)):
        secs = int(end_time - time.time())
    else:
        end = datetime.strptime(end_time, FMT).replace(tzinfo=timezone.utc)
        secs = int((end - datetime.now(timezone.utc)).total_seconds())
    if secs <= 0:
        return "Closed"
    hours, rest = divmod(secs, 3600)
    mins, secs = divmod(rest, 60)
    return f"{hours}:{mins:02d}:{secs:02d}"


def next_minimum(item):
    if "next_minimum" in item:
        return item["next_minimum"]        
    if item["current_price"] is None:
        return item["starting_price"]
    return item["current_price"] + item["min_increment"]


class BidderPage(QWidget):
    def __init__(self, link):
        super().__init__()
        self.link = link
        self.items = {}

        self.welcome = QLabel("")
        self.welcome.setStyleSheet("font-size: 16px; font-weight: bold;")
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.load)
        top = QHBoxLayout()
        top.addWidget(self.welcome)
        top.addStretch()
        top.addWidget(refresh)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.on_select)

        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 2_147_483_647)
        self.amount.setDecimals(0)
        self.amount.setPrefix("₱ ")
        bid_btn = QPushButton("Place bid")
        bid_btn.clicked.connect(self.place_bid)
        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("Your bid:"))
        bottom.addWidget(self.amount)
        bottom.addWidget(bid_btn)
        bottom.addStretch()

        self.status = QLabel("")

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.table)
        layout.addLayout(bottom)
        layout.addWidget(self.status)

        self.clock = QTimer(self)
        self.clock.timeout.connect(self.tick)
        self.clock.start(1000)

    def start(self, user):
        self.welcome.setText(f"Bidder: {user['username']}")
        self.load()

    def on_message(self, topic, payload):
        kind = payload.get("type")
        if kind == "list_items_reply" and payload.get("ok"):
            self.items = {i["id"]: i for i in payload["data"]}
            self.fill_table()
        elif kind == "place_bid_reply":
            if payload.get("ok"):
                item = payload["data"]
                self.items[item["id"]] = item
                self.fill_table()
                self.set_status("Bid placed!", good=True)
            else:
                self.set_status(payload.get("error") or "Bid rejected.", good=False)
        elif kind in ("bid_accepted", "auction_opened"):
            item = payload["item"]
            self.items[item["id"]] = item
            self.fill_table()
        elif kind == "auction_closed":
            item = payload["item"]
            self.items.pop(item["id"], None)
            self.fill_table()
            winner = item.get("winner_name") or "no winner"
            self.set_status(f"'{item['title']}' closed. Winner: {winner}", good=True)

    def load(self):
        self.link.send({"type": m.LIST_ITEMS, "status": "open"})

    def selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        return int(self.table.item(row, 0).text())

    def on_select(self):
        item = self.items.get(self.selected_id())
        if item:
            self.amount.setValue(next_minimum(item))

    def place_bid(self):
        item_id = self.selected_id()
        if item_id is None:
            self.set_status("Select an item first.", good=False)
            return
        self.link.send({"type": m.PLACE_BID, "item_id": item_id, "amount": self.amount.value()})

    def set_status(self, text, good):
        self.status.setStyleSheet("color: green;" if good else "color: red;")
        self.status.setText(text)

    def fill_table(self):
        keep = self.selected_id()
        self.table.blockSignals(True)   
        self.table.setRowCount(0)
        for item in self.items.values():
            row = self.table.rowCount()
            self.table.insertRow(row)
            price = "No bids" if item["current_price"] is None else f"{item['current_price']:.0f}"
            cells = [item["id"], item["title"], price, f"{next_minimum(item):.0f}",
                     time_left(item["end_time"]), item.get("winner_name") or "-"]
            for col, value in enumerate(cells):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
            if item["id"] == keep:
                self.table.selectRow(row)
        self.table.blockSignals(False)

    def tick(self):
        for row in range(self.table.rowCount()):
            item = self.items.get(int(self.table.item(row, 0).text()))
            if item:
                self.table.item(row, 4).setText(time_left(item["end_time"]))