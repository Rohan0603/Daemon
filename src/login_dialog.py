import random
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit,
    QPushButton, QLabel, QWidget,
)
from PyQt6.QtCore import Qt


def _butcher_email(email: str) -> str:
    local = email.split("@")[0]
    if len(local) >= 3:
        vowels = "aeiou"
        idx = random.randint(1, len(local) - 2)
        new_char = random.choice(vowels)
        local = local[:idx] + new_char + local[idx + 1:]
        return local
    else:
        return local + str(random.randint(0, 9))


class LoginDialog(QDialog):
    def __init__(
        self,
        on_sign_in: Optional[Callable[[str, str], Optional[str]]] = None,
        on_sign_up: Optional[Callable[[str, str], Optional[str]]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._on_sign_in = on_sign_in
        self._on_sign_up = on_sign_up
        self._mode = "signin"

        self.setWindowTitle("Daemon: Clearance Check")
        self.setFixedSize(300, 250)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout()
        layout.setSpacing(10)

        title = QLabel("Daemon: Clearance Check")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        self._email_input = QLineEdit()
        self._email_input.setPlaceholderText("Email. And don't mess this up, man.")
        layout.addWidget(self._email_input)

        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText("Password. No peeking.")
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._password_input)

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: red; font-size: 12px;")
        self._error_label.setVisible(False)
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        self._action_btn = QPushButton("Access the Brain")
        self._action_btn.setDefault(True)
        self._action_btn.clicked.connect(self._on_action)
        self._email_input.returnPressed.connect(self._password_input.setFocus)
        self._password_input.returnPressed.connect(self._on_action)
        layout.addWidget(self._action_btn)

        self._toggle_btn = QPushButton("Wait, I need a new identity!")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet("QPushButton { border: none; color: #5B8DEF; }")
        self._toggle_btn.clicked.connect(self._toggle_mode)
        layout.addWidget(self._toggle_btn)

        layout.addStretch()
        self.setLayout(layout)

    def _toggle_mode(self) -> None:
        if self._mode == "signin":
            self._mode = "signup"
            self.setWindowTitle("Daemon: Identity Registration")
            self._action_btn.setText("Register Identity")
            self._toggle_btn.setText("Oh wait, I already have one!")
        else:
            self._mode = "signin"
            self.setWindowTitle("Daemon: Clearance Check")
            self._action_btn.setText("Access the Brain")
            self._toggle_btn.setText("Wait, I need a new identity!")
        title_label = self.findChild(QLabel)
        if title_label:
            title_label.setText(self.windowTitle())
        self._error_label.setVisible(False)

    def _on_action(self) -> None:
        email = self._email_input.text().strip()
        password = self._password_input.text()
        if not email or not password:
            self.show_error("")
            return

        handler = self._on_sign_in if self._mode == "signin" else self._on_sign_up
        if handler is None:
            return

        self.set_loading(True)
        try:
            uid = handler(email, password)
            if uid is not None:
                self.accept()
            elif "@" in email and "." in email:
                butchered = _butcher_email(email)
                self.show_error(f"You call that an email? '{butchered}'? Geez, man.")
            else:
                self.show_error("That ain't it, chief. You're locked out.")
        except Exception:
            self.show_error("Brain's offline. Can't reach Firebase.")
        finally:
            self.set_loading(False)

    def get_credentials(self) -> tuple[str, str]:
        return (self._email_input.text().strip(), self._password_input.text())

    def show_error(self, message: str) -> None:
        if not message:
            message = "That ain't it, chief. You're locked out."
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def set_loading(self, loading: bool) -> None:
        self._action_btn.setEnabled(not loading)
        self._action_btn.setText(
            "Please wait..." if loading else (
                "Register Identity" if self._mode == "signup" else "Access the Brain"
            )
        )
