import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import requests
from src.firebase_auth import FirebaseAuth


@pytest.fixture
def auth(tmp_path: Path) -> FirebaseAuth:
    token_path = tmp_path / ".daemon_auth.json"
    return FirebaseAuth(api_key="test-key", project_id="test-project", token_path=token_path)


def test_sign_in_success(auth: FirebaseAuth) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "idToken": "id1", "refreshToken": "rt1",
        "localId": "uid1", "email": "a@b.com", "expiresIn": "3600",
    }
    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = auth.sign_in("a@b.com", "pass123")

    mock_post.assert_called_once()
    assert result == "uid1"
    assert auth.uid == "uid1"
    assert auth.email == "a@b.com"
    saved = json.loads(auth._token_path.read_text(encoding="utf-8"))
    assert saved["uid"] == "uid1"


def test_sign_in_wrong_password(auth: FirebaseAuth) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error": {"message": "INVALID_LOGIN_CREDENTIALS"}}
    with patch("requests.post", return_value=mock_resp):
        result = auth.sign_in("a@b.com", "wrong")
    assert result is None
    assert auth.uid is None


def test_sign_up_success(auth: FirebaseAuth) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "idToken": "id2", "refreshToken": "rt2",
        "localId": "uid2", "email": "new@b.com", "expiresIn": "3600",
    }
    with patch("requests.post", return_value=mock_resp):
        result = auth.sign_up("new@b.com", "pass456")
    assert result == "uid2"


def test_sign_up_existing_email(auth: FirebaseAuth) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error": {"message": "EMAIL_EXISTS"}}
    with patch("requests.post", return_value=mock_resp):
        result = auth.sign_up("exists@b.com", "pass")
    assert result is None


def test_refresh_token(auth: FirebaseAuth) -> None:
    auth._refresh_token = "old_rt"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id_token": "new_id", "refresh_token": "new_rt",
        "expires_in": "3600",
    }
    with patch("requests.post", return_value=mock_resp):
        ok = auth.refresh()
    assert ok
    assert auth.id_token == "new_id"


def test_get_valid_token_refreshes_when_expired(auth: FirebaseAuth) -> None:
    auth._id_token = "old_id"
    auth._refresh_token = "old_rt"
    auth._expires_at = 100
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id_token": "refreshed_id", "refresh_token": "new_rt",
        "expires_in": "3600",
    }
    with patch("requests.post", return_value=mock_resp):
        token = auth.get_valid_token()
    assert token == "refreshed_id"


def test_get_valid_token_returns_cached_when_valid(auth: FirebaseAuth) -> None:
    auth._id_token = "good_id"
    auth._expires_at = 9999999999
    with patch("requests.post") as mock_post:
        token = auth.get_valid_token()
    assert token == "good_id"
    mock_post.assert_not_called()


def test_load_auth_restores_tokens(auth: FirebaseAuth) -> None:
    saved = {"uid": "u1", "email": "a@b.com", "idToken": "tid", "refreshToken": "trt", "expires_at": 99999}
    auth._token_path.write_text(json.dumps(saved), encoding="utf-8")
    ok = auth.load()
    assert ok
    assert auth.uid == "u1"
    assert auth.email == "a@b.com"


def test_is_authenticated(auth: FirebaseAuth) -> None:
    assert not auth.is_authenticated()
    auth._uid = "u1"
    auth._id_token = "t"
    auth._expires_at = 99999
    assert auth.is_authenticated()


def test_clear(auth: FirebaseAuth) -> None:
    auth._uid = "u1"
    auth._token_path.write_text(json.dumps({"uid": "u1"}), encoding="utf-8")
    auth.clear()
    assert not auth.is_authenticated()
    assert not auth._token_path.exists()


def test_network_error_returns_none(auth: FirebaseAuth) -> None:
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("connection refused")):
        result = auth.sign_in("a@b.com", "pass")
    assert result is None
