import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import requests
from src.firebase_auth import FirebaseAuth
from src.events import EventBus, EventType


@pytest.fixture
def auth(tmp_path: Path) -> FirebaseAuth:
    token_path = tmp_path / ".daemon_auth.json"
    instance = FirebaseAuth(api_key="test-key", project_id="test-project", token_path=token_path)
    instance._auth_backend_url = "https://auth.example.test"
    return instance


def test_sign_in_success(auth: FirebaseAuth) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id_token": "id1", "refresh_token": "rt1",
        "uid": "uid1", "email": "a@b.com", "expires_in": "3600",
    }
    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = auth.sign_in("a@b.com", "pass123")

    mock_post.assert_called_once()
    assert result == "uid1"
    assert auth.uid == "uid1"
    assert auth.email == "a@b.com"
    saved = json.loads(auth._token_path.read_text(encoding="utf-8"))
    assert saved["format"] in {"dpapi-v1", "plain-v1"}


def test_sign_in_wrong_password(auth: FirebaseAuth) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error": {"message": "INVALID_LOGIN_CREDENTIALS"}}
    with patch("requests.post", return_value=mock_resp):
        result = auth.sign_in("a@b.com", "wrong")
    assert result is None
    assert auth.uid is None
    assert auth.last_error_code == "INVALID_LOGIN_CREDENTIALS"


def test_sign_up_success(auth: FirebaseAuth) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id_token": "id2", "refresh_token": "rt2",
        "uid": "uid2", "email": "new@b.com", "expires_in": "3600",
    }
    with patch("requests.post", return_value=mock_resp):
        result = auth.sign_up("new@b.com", "pass456")
    assert result == "uid2"


def test_sign_in_without_remember_me_does_not_persist(auth: FirebaseAuth) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id_token": "id2", "refresh_token": "rt2",
        "uid": "uid2", "email": "new@b.com", "expires_in": "3600",
    }
    with patch("requests.post", return_value=mock_resp):
        result = auth.sign_in("new@b.com", "pass456", remember_me=False)
    assert result == "uid2"
    assert not auth._token_path.exists()
    assert auth.uid == "uid2"


def test_sign_up_existing_email(auth: FirebaseAuth) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error": {"message": "EMAIL_EXISTS"}}
    with patch("requests.post", return_value=mock_resp):
        result = auth.sign_up("exists@b.com", "pass")
    assert result is None
    assert auth.last_error_code == "EMAIL_EXISTS"


def test_backend_sign_in_does_not_use_firebase_api_key(auth: FirebaseAuth) -> None:
    auth._auth_backend_url = "https://auth.example.test"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "uid": "uid-backend",
        "id_token": "id-backend",
        "refresh_token": "refresh-backend",
        "expires_in": 3600,
    }
    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = auth.sign_in("a@b.com", "pass123")
    assert result == "uid-backend"
    assert mock_post.call_args.args[0] == "https://auth.example.test/auth/sign-in"
    assert "key" not in mock_post.call_args.args[0]


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


def test_sign_out_clears_auth(auth: FirebaseAuth) -> None:
    auth._uid = "u1"
    auth._id_token = "token"
    auth.sign_out()
    assert not auth.is_authenticated()


def test_load_does_not_write_uid_to_config(auth: FirebaseAuth, monkeypatch) -> None:
    saved = {"uid": "u1", "email": "a@b.com", "idToken": "tid", "refreshToken": "trt", "expires_at": 99999}
    auth._token_path.write_text(json.dumps(saved), encoding="utf-8")
    save_config = MagicMock()
    monkeypatch.setattr("src.firebase_auth.save_config", save_config, raising=False)
    assert auth.load()
    save_config.assert_not_called()


def test_network_error_returns_none(auth: FirebaseAuth) -> None:
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("connection refused")):
        result = auth.sign_in("a@b.com", "pass")
    assert result is None


@pytest.fixture
def auth_with_bus(tmp_path: Path) -> FirebaseAuth:
    token_path = tmp_path / ".daemon_auth.json"
    bus = EventBus()
    instance = FirebaseAuth(api_key="test-key", project_id="test-project", token_path=token_path, event_bus=bus)
    instance._auth_backend_url = "https://auth.example.test"
    return instance


def test_sign_in_emits_auth_success_event(auth_with_bus: FirebaseAuth) -> None:
    bus = auth_with_bus._event_bus
    events = []
    bus.subscribe(EventType.AUTH_SUCCESS, lambda e: events.append(e))
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id_token": "id1", "refresh_token": "rt1",
        "uid": "uid1", "email": "a@b.com", "expires_in": "3600",
    }
    with patch("requests.post", return_value=mock_resp):
        auth_with_bus.sign_in("a@b.com", "pass123")
    
    assert len(events) == 1
    assert events[0].type == EventType.AUTH_SUCCESS
    assert events[0].data["uid"] == "uid1"


def test_sign_in_failure_emits_auth_failure_event(auth_with_bus: FirebaseAuth) -> None:
    bus = auth_with_bus._event_bus
    events = []
    bus.subscribe(EventType.AUTH_FAILURE, lambda e: events.append(e))
    
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error": {"message": "INVALID_LOGIN_CREDENTIALS"}}
    with patch("requests.post", return_value=mock_resp):
        auth_with_bus.sign_in("a@b.com", "wrong")
    
    assert len(events) == 1
    assert events[0].type == EventType.AUTH_FAILURE
    assert events[0].data["reason"] == "backend_http_400"


def test_refresh_emits_token_refreshed_event(auth_with_bus: FirebaseAuth) -> None:
    bus = auth_with_bus._event_bus
    events = []
    bus.subscribe(EventType.TOKEN_REFRESHED, lambda e: events.append(e))
    
    auth_with_bus._refresh_token = "old_rt"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id_token": "new_id", "refresh_token": "new_rt",
        "expires_in": "3600",
    }
    with patch("requests.post", return_value=mock_resp):
        auth_with_bus.refresh()
    
    assert len(events) == 1
    assert events[0].type == EventType.TOKEN_REFRESHED


def test_clear_emits_auth_cleared_event(auth_with_bus: FirebaseAuth) -> None:
    bus = auth_with_bus._event_bus
    events = []
    bus.subscribe(EventType.AUTH_CLEARED, lambda e: events.append(e))
    
    auth_with_bus._uid = "u1"
    auth_with_bus.clear()
    
    assert len(events) == 1
    assert events[0].type == EventType.AUTH_CLEARED


def test_no_event_bus_does_not_crash(auth: FirebaseAuth) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "idToken": "id1", "refreshToken": "rt1",
        "localId": "uid1", "email": "a@b.com", "expiresIn": "3600",
    }
    with patch("requests.post", return_value=mock_resp):
        result = auth.sign_in("a@b.com", "pass123")
    
    assert result == "uid1"


def test_direct_firebase_sign_in_uses_identity_toolkit(auth: FirebaseAuth) -> None:
    auth._auth_backend_url = ""
    auth._web_api_key = "web-key"
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "localId": "direct-uid", "idToken": "direct-id",
        "refreshToken": "direct-refresh", "expiresIn": "3600",
        "email": "a@b.com",
    }
    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = auth.sign_in("a@b.com", "pass123")

    assert result == "direct-uid"
    assert mock_post.call_args.args[0] == (
        "https://identitytoolkit.googleapis.com/v1/accounts:"
        "signInWithPassword?key=web-key"
    )
    assert mock_post.call_args.kwargs["json"]["returnSecureToken"] is True


def test_explicit_api_key_enables_direct_firebase(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("src.firebase_auth.load_config", lambda validate=False: {
        "firebase": {"project_id": "project-id"},
    })
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "localId": "explicit-uid",
        "idToken": "explicit-id",
        "refreshToken": "explicit-refresh",
        "expiresIn": "3600",
    }
    post = MagicMock(return_value=response)
    monkeypatch.setattr("src.firebase_auth.requests.post", post)
    auth = FirebaseAuth(api_key="explicit-key", token_path=tmp_path / "token")

    assert auth.sign_in("user@example.com", "password", remember_me=False) == "explicit-uid"
    assert "key=explicit-key" in post.call_args.args[0]


def test_direct_firebase_refresh_uses_secure_token_endpoint(auth: FirebaseAuth) -> None:
    auth._auth_backend_url = ""
    auth._web_api_key = "web-key"
    auth._refresh_token = "old-refresh"
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "user_id": "direct-uid", "id_token": "new-id",
        "refresh_token": "new-refresh", "expires_in": "3600",
    }
    with patch("requests.post", return_value=mock_resp) as mock_post:
        assert auth.refresh()

    assert mock_post.call_args.args[0] == (
        "https://securetoken.googleapis.com/v1/token?key=web-key"
    )
    assert mock_post.call_args.kwargs["data"] == {
        "grant_type": "refresh_token", "refresh_token": "old-refresh",
    }
