import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QApplication, QComboBox, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

import messages as m
from bidder_page import BidderPage
from seller_page import SellerPage

from backend_link import start_link


class LoginPage(QWidget):
    def __init__(self, link):
        super().__init__()
        self.link = link
        self.waiting = False

        title = QLabel("LAN Auction")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")

        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.role = QComboBox()
        self.role.addItems(["bidder", "seller"])

        form = QFormLayout()
        form.addRow("Username", self.username)
        form.addRow("Login key", self.password)
        form.addRow("Register as", self.role)

        login_btn = QPushButton("Login")
        register_btn = QPushButton("Register")
        login_btn.clicked.connect(self.do_login)
        register_btn.clicked.connect(self.do_register)
        buttons = QHBoxLayout()
        buttons.addWidget(login_btn)
        buttons.addWidget(register_btn)

        box = QVBoxLayout()
        box.addStretch()
        box.addWidget(title)
        box.addLayout(form)
        box.addLayout(buttons)
        box.addStretch()

        outer = QHBoxLayout(self)
        outer.addStretch()
        outer.addLayout(box)
        outer.addStretch()

    def do_login(self):
        self.link.send({"type": m.LOGIN, "username": self.username.text(),
                        "password": self.password.text()})
        self.waiting = True
        QTimer.singleShot(5000, self.no_reply)

    def no_reply(self):
        if self.waiting:
            self.waiting = False
            QMessageBox.warning(self, "No reply from server",
                                "Is the backplane running, and is server.py running?\n"
                                "Check BACKPLANE_IP in messages.py.")

    def do_register(self):
        self.link.send({"type": m.REGISTER, "username": self.username.text(),
                        "password": self.password.text(), "role": self.role.currentText()})

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LAN Auction")
        self.resize(800, 500)
        self.link = start_link()
        self.user = None
        menu = self.menuBar().addMenu("Account")
        menu.addAction("Logout").triggered.connect(self.logout)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.login_page = LoginPage(self.link)
        self.home_page = QLabel("")
        self.bidder_page = BidderPage(self.link)
        self.seller_page = SellerPage(self.link)
        self.stack.addWidget(self.login_page)
        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.bidder_page)
        self.stack.addWidget(self.seller_page)
        
        self.bid_popup = QLabel(self)
        self.bid_popup.setTextFormat(Qt.TextFormat.PlainText)
        self.bid_popup.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.bid_popup.setWordWrap(True)
        self.bid_popup.setFixedWidth(290)
        self.bid_popup.setStyleSheet("""
            background-color: #203449;
            color: white;
            border: 1px solid #6687a3;
            border-radius: 8px;
            padding: 10px;
        """)
        self.bid_popup.hide()

        self.popup_timer = QTimer(self)
        self.popup_timer.setSingleShot(True)
        self.popup_timer.timeout.connect(self.bid_popup.hide)

        self.timer = QTimer(self)             
        self.timer.timeout.connect(self.poll)
        self.timer.start(100)
        
    def show_bid_popup(self, item, previous_leader):
        username = self.user["username"]
        bidder = item["winner_name"]
        title = item["title"]
        price = f"₱{item['current_price']:,}"

        if bidder == username:
            text = f"Your {price} bid on {title} was accepted."
        elif previous_leader == username:
            text = f"You were outbid on {title}. Current bid: {price}."
        elif item.get("seller_name") == username:
            text = f"{bidder} bid {price} on your listing: {title}."
        else:
            text = f"{bidder} bid {price} on {title}."

        self.bid_popup.setText(text)
        self.bid_popup.adjustSize()
        self.bid_popup.move(
            max(0, self.width() - self.bid_popup.width() - 16),
            self.menuBar().height() + 12,
        )
        self.bid_popup.show()
        self.bid_popup.raise_()
        self.popup_timer.start(3000)

    def logout(self):
        self.user = None
        self.login_page.password.clear()
        self.stack.setCurrentWidget(self.login_page)

    def poll(self):
        while not self.link.inbox.empty():
            topic, payload = self.link.inbox.get()
            self.handle(topic, payload)

    def handle(self, topic, payload):
        kind = payload.get("type")
        if kind == "login_reply":
            self.login_page.waiting = False
            if payload.get("ok"):
                self.user = payload["data"]["user"]
                self.show_home()
            else:
                QMessageBox.critical(self, "Login failed", payload.get("error") or "Unknown error")
        elif kind == "register_reply":
            if payload.get("ok"):
                QMessageBox.information(self, "Registered", "Account created. You can log in now.")
            else:
                QMessageBox.critical(self, "Error", payload.get("error") or "Unknown error")
        elif self.user and self.user["role"] == "bidder":
            self.bidder_page.on_message(topic, payload)
        elif self.user and self.user["role"] == "seller":
            self.seller_page.on_message(topic, payload)

    def show_home(self):
        if self.user["role"] == "bidder":
            self.stack.setCurrentWidget(self.bidder_page)
            self.bidder_page.start(self.user)
        elif self.user["role"] == "seller":
            self.stack.setCurrentWidget(self.seller_page)
            self.seller_page.start(self.user)
        else:
            self.home_page.setText(f"Welcome {self.user['username']} ({self.user['role']})")
            self.stack.setCurrentWidget(self.home_page)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())