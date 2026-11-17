from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QAbstractItemView, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

import messages as m
from bidder_page import time_left

COLUMNS = ["ID", "Item", "Status", "Starting price", "Current price", "Time left",
           "Leader / Winner"]


class SellerPage(QWidget):
    def __init__(self, link):
        super().__init__()
        self.link = link
        self.username = ""
        self.items = {}
        
        self.welcome = QLabel("")
        self.welcome.setStyleSheet("font-size: 16px; font-weight: bold;")
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.load)
        top = QHBoxLayout()
        top.addWidget(self.welcome)
        top.addStretch()
        top.addWidget(refresh)

        self.title = QLineEdit()
        self.start_price = QSpinBox()
        self.start_price.setRange(0, 2_147_483_647)
        self.start_price.setPrefix("₱ ")
        submit = QPushButton("Create listing")
        submit.clicked.connect(self.submit)
        form = QFormLayout()
        form.addRow("Item name", self.title)
        form.addRow("Starting price", self.start_price)
        form.addRow("", submit)
        note = QLabel("Each auction closes 60 seconds after the last accepted bid.")
        note.setStyleSheet("color: gray;")

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.status = QLabel("")

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(QLabel("My listings"))
        layout.addWidget(self.table)
        layout.addWidget(self.status)

        self.clock = QTimer(self)
        self.clock.timeout.connect(self.tick)
        self.clock.start(1000)

    def start(self, user):
        self.username = user["username"]
        self.items = {}
        self.table.setRowCount(0)
        self.welcome.setText(f"Seller: {self.username}")
        self.load()

    def on_message(self, topic, payload):
        kind = payload.get("type")
        if kind == "list_items_reply" and payload.get("ok"):
            mine = {i["id"]: i for i in payload["data"] if i.get("seller_name") == self.username}
            for old_id, old in self.items.items():
                if old_id not in mine:
                    mine[old_id] = dict(old, status="closed")
            self.items = mine
            self.fill_table()
        elif kind == "create_listing_reply":
            if payload.get("ok"):
                item = payload["data"]
                self.items[item["id"]] = item
                self.fill_table()
                self.title.clear()
                self.start_price.setValue(0)
                self.set_status("Listing created. Bidding is open.", good=True)
            else:
                self.set_status(payload.get("error") or "Could not create listing.", good=False)
        elif kind in ("bid_accepted", "auction_opened", "auction_closed"):
            item = payload["item"]
            if item.get("seller_name") == self.username:
                self.items[item["id"]] = item
                self.fill_table()
                if kind == "auction_closed":
                    winner = item.get("winner_name") or "no winner"
                    self.set_status(f"'{item['title']}' closed. Winner: {winner}", good=True)
    def load(self):
        self.link.send({"type": m.LIST_ITEMS})

    def submit(self):
        title = self.title.text().strip()
        if not title:
            self.set_status("Please enter an item name.", good=False)
            return
        self.link.send({"type": m.CREATE_LISTING, "title": title,
                        "starting_price": self.start_price.value()})

    # ---------- drawing
    def set_status(self, text, good):
        self.status.setStyleSheet("color: green;" if good else "color: red;")
        self.status.setText(text)

    def fill_table(self):
        self.table.setRowCount(0)
        for item in self.items.values():
            row = self.table.rowCount()
            self.table.insertRow(row)
            current = "-" if item["current_price"] is None else f"{item['current_price']:.0f}"
            is_open = item["status"] == "open"
            cells = [item["id"], item["title"], "Open" if is_open else "Closed",
                     f"{item['starting_price']:.0f}", current,
                     time_left(item["end_time"]) if is_open else "-",
                     item.get("winner_name") or "-"]
            for col, value in enumerate(cells):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))

    def tick(self):
        for row in range(self.table.rowCount()):
            item = self.items.get(int(self.table.item(row, 0).text()))
            if item and item["status"] == "open":
                self.table.item(row, 5).setText(time_left(item["end_time"]))