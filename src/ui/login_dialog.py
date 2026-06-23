import logging
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit,
    QPushButton, QLabel, QWidget,
)
from PyQt6.QtCore import Qt


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

        self.setWindowTitle("Daemon: Authentication")
        self.setFixedSize(300, 250)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout()
        layout.setSpacing(10)

        title = QLabel("Daemon: Authentication")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        self._email_input = QLineEdit()
        self._email_input.setPlaceholderText("Email")
        layout.addWidget(self._email_input)

        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText("Password")
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._password_input)

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: red; font-size: 12px;")
        self._error_label.setVisible(False)
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        self._action_btn = QPushButton("Sign In")
        self._action_btn.setDefault(True)
        self._action_btn.clicked.connect(self._on_action)
        self._email_input.returnPressed.connect(self._password_input.setFocus)
        self._password_input.returnPressed.connect(self._on_action)
        layout.addWidget(self._action_btn)

        self._toggle_btn = QPushButton("Create an account")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet("QPushButton { border: none; color: #5B8DEF; }")
        self._toggle_btn.clicked.connect(self._toggle_mode)
        layout.addWidget(self._toggle_btn)

        layout.addStretch()
        self.setLayout(layout)

    def _toggle_mode(self) -> None:
        if self._mode == "signin":
            self._mode = "signup"
            self.setWindowTitle("Daemon: Registration")
            self._action_btn.setText("Sign Up")
            self._toggle_btn.setText("Already have an account? Sign In")
        else:
            self._mode = "signin"
            self.setWindowTitle("Daemon: Authentication")
            self._action_btn.setText("Sign In")
            self._toggle_btn.setText("Create an account")
        title_label = self.findChild(QLabel)
        if title_label:
            title_label.setText(self.windowTitle())
        self._error_label.setVisible(False)

    def _on_action(self) -> None:
        email = self._email_input.text().strip()
        password = self._password_input.text()
        if not email or not password:
            self.show_error("Please enter both email and password.")
            return

        handler = self._on_sign_in if self._mode == "signin" else self._on_sign_up
        if handler is None:
            return

        self.set_loading(True)
        try:
            uid = handler(email, password)
            if uid is not None:
                self.accept()
            elif "@" not in email or "." not in email:
                self.show_error("Please enter a valid email address.")
            else:
                if self._mode == "signin":
                    self.show_error("Authentication failed. Please check your credentials.")
                else:
                    self.show_error("Registration failed. Email may already be in use.")
        except Exception as e:
            logging.getLogger(__name__).exception("Login failed with exception: %s", e)
            self.show_error("Connection error. Could not reach authentication service.")
        finally:
            self.set_loading(False)

    def get_credentials(self) -> tuple[str, str]:
        return (self._email_input.text().strip(), self._password_input.text())

    def show_error(self, message: str) -> None:
        if not message:
            message = "Authentication failed."
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def set_loading(self, loading: bool) -> None:
        self._action_btn.setEnabled(not loading)
        self._action_btn.setText(
            "Please wait..." if loading else (
                "Sign Up" if self._mode == "signup" else "Sign In"
            )
        )
