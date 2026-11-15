import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QApplication, QComboBox, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

import messages as m
from bidder_page import BidderPage

USE_FAKE = True   #For testing
if USE_FAKE:
    from fake_link import start_link
else:
    from banyan_link import start_link


class LoginPage(QWidget):
    def __init__(self, link):
        super().__init__()
        self.link = link

        title = QLabel("LAN Auction")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")

        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.role = QComboBox()
        self.role.addItems(["bidder", "seller"])

        form = QFormLayout()
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
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

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.login_page = LoginPage(self.link)
        self.home_page = QLabel("")
        self.bidder_page = BidderPage(self.link)
        self.stack.addWidget(self.login_page)
        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.bidder_page)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(100)

    def poll(self):
        while not self.link.inbox.empty():
            topic, payload = self.link.inbox.get()
            self.handle(topic, payload)

    def handle(self, topic, payload):
        kind = payload.get("type")
        if kind == "login_reply":
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

    def show_home(self):
        if self.user["role"] == "bidder":
            self.stack.setCurrentWidget(self.bidder_page)
            self.bidder_page.start(self.user)
        else:
            self.home_page.setText(f"Welcome {self.user['username']} ({self.user['role']})")
            self.stack.setCurrentWidget(self.home_page)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())