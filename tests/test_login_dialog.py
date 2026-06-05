import pytest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.login_dialog import LoginDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication([])
    yield app


@pytest.fixture
def dialog(qapp):
    return LoginDialog()


def test_initial_mode_is_sign_in(dialog: LoginDialog) -> None:
    assert dialog._mode == "signin"
    assert dialog._action_btn.text() == "Access the Brain"


def test_toggle_to_sign_up(dialog: LoginDialog) -> None:
    dialog._toggle_mode()
    assert dialog._mode == "signup"
    assert dialog._action_btn.text() == "Register Identity"
    assert dialog._toggle_btn.text() == "Oh wait, I already have one!"


def test_toggle_back_to_sign_in(dialog: LoginDialog) -> None:
    dialog._toggle_mode()
    dialog._toggle_mode()
    assert dialog._mode == "signin"
    assert dialog._action_btn.text() == "Access the Brain"


def test_get_credentials(dialog: LoginDialog) -> None:
    dialog._email_input.setText("test@example.com")
    dialog._password_input.setText("p@ss123")
    email, password = dialog.get_credentials()
    assert email == "test@example.com"
    assert password == "p@ss123"


def test_show_error(dialog: LoginDialog) -> None:
    dialog.show()
    dialog.show_error("Wrong password")
    assert dialog._error_label.text() == "Wrong password"
    assert dialog._error_label.isVisible()


def test_set_loading(dialog: LoginDialog) -> None:
    dialog.set_loading(True)
    assert not dialog._action_btn.isEnabled()
    assert dialog._action_btn.text() == "Please wait..."
    dialog.set_loading(False)
    assert dialog._action_btn.isEnabled()
    assert dialog._action_btn.text() == "Access the Brain"


def test_set_loading_in_signup_mode(dialog: LoginDialog) -> None:
    dialog._toggle_mode()  # now in signup
    dialog.set_loading(True)
    assert dialog._action_btn.text() == "Please wait..."
    dialog.set_loading(False)
    assert dialog._action_btn.text() == "Register Identity"


def test_empty_fields_shows_error(dialog: LoginDialog) -> None:
    dialog.show()
    dialog._on_action()
    assert dialog._error_label.isVisible()
    assert "locked out" in dialog._error_label.text()


def test_butcher_email_swaps_vowel(qtbot):
    from src.login_dialog import _butcher_email
    result = _butcher_email("test@foo.com")
    assert "@" not in result
    assert len(result) == len("test")


def test_butcher_email_appends_digit(qtbot):
    from src.login_dialog import _butcher_email
    result = _butcher_email("ab@foo.com")
    assert any(ch.isdigit() for ch in result)


def test_persona_signin_error(qtbot):
    dlg = LoginDialog()
    qtbot.add_widget(dlg)
    dlg._mode = "signin"
    handler = MagicMock(return_value=None)
    dlg._on_sign_in = handler
    dlg._email_input.setText("x@ycom")
    dlg._password_input.setText("pwd")
    dlg._on_action()
    assert "locked out" in dlg._error_label.text()
