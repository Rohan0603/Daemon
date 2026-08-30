from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from src.firebase_crud import FirebaseCRUD


@pytest.fixture
def auth() -> MagicMock:
    instance = MagicMock()
    instance.get_valid_token.return_value = "test-token"
    instance.auth_backend_url = "https://api.example.test"
    return instance


@pytest.fixture
def crud(auth: MagicMock) -> FirebaseCRUD:
    return FirebaseCRUD(auth=auth, project_id="test-project")


def test_get_document_exists(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    response.json.return_value = {"data": {"key": "val"}}
    monkeypatch.setattr(crud._session, "request", MagicMock(return_value=response))

    result = crud.get("c", "d")

    assert result == {"key": "val"}
    call = crud._session.request.call_args
    assert call.args[:2] == ("GET", "https://api.example.test/data/document")
    assert call.kwargs["headers"]["Authorization"] == "Bearer test-token"
    assert call.kwargs["params"] == {"collection": "c", "doc_id": "d"}


def test_get_document_not_found(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=404)
    monkeypatch.setattr(crud._session, "request", MagicMock(return_value=response))

    result = crud.get("c", "missing")

    assert result is None


def test_get_network_error_returns_none(crud: FirebaseCRUD, monkeypatch) -> None:
    monkeypatch.setattr(crud._session, "request", MagicMock(side_effect=Exception("timeout")))

    result = crud.get("c", "d")

    assert result is None
    assert crud.available


def test_set_no_merge(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    request = MagicMock(return_value=response)
    monkeypatch.setattr(crud._session, "request", request)

    ok = crud.set("c", "d", {"key": "val"}, merge=False)

    assert ok is True
    assert request.call_args.args[:2] == ("PATCH", "https://api.example.test/data/document")
    assert request.call_args.kwargs["json"] == {
        "collection": "c",
        "doc_id": "d",
        "data": {"key": "val"},
        "merge": False,
    }


def test_set_with_merge_preserves_existing(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    request = MagicMock(return_value=response)
    monkeypatch.setattr(crud._session, "request", request)

    ok = crud.set("c", "d", {"key": "new"}, merge=True)

    assert ok is True
    assert request.call_args.kwargs["json"]["merge"] is True


def test_add_document(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    response.json.return_value = {"id": "auto123"}
    request = MagicMock(return_value=response)
    monkeypatch.setattr(crud._session, "request", request)

    doc_id = crud.add("c", {"text": "hello"})

    assert doc_id == "auto123"
    assert request.call_args.args[:2] == ("POST", "https://api.example.test/data/collection")
    assert request.call_args.kwargs["json"] == {"collection": "c", "data": {"text": "hello"}}


def test_delete_document(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    request = MagicMock(return_value=response)
    monkeypatch.setattr(crud._session, "request", request)

    ok = crud.delete("c", "d")

    assert ok is True
    assert request.call_args.args[:2] == ("DELETE", "https://api.example.test/data/document")
    assert request.call_args.kwargs["params"] == {"collection": "c", "doc_id": "d"}


def test_query_collection(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    response.json.return_value = {"documents": [{"x": "a"}, {"x": "b"}]}
    request = MagicMock(return_value=response)
    monkeypatch.setattr(crud._session, "request", request)

    docs = crud.query("c")

    assert docs == [{"x": "a"}, {"x": "b"}]
    assert request.call_args.args[:2] == ("GET", "https://api.example.test/data/query")
    assert request.call_args.kwargs["params"] == {"collection": "c", "ascending": "true"}


def test_query_empty_collection(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    response.json.return_value = {"documents": []}
    monkeypatch.setattr(crud._session, "request", MagicMock(return_value=response))

    assert crud.query("c") == []


def test_read_all_text(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    response.json.return_value = {"documents": [{"text": "hello"}, {"text": "world"}]}
    monkeypatch.setattr(crud._session, "request", MagicMock(return_value=response))

    assert crud.read_all_text("c") == ["hello", "world"]


def test_retry_succeeds_on_second_attempt(crud: FirebaseCRUD, monkeypatch) -> None:
    response = MagicMock(status_code=200)
    response.json.return_value = {"data": {"x": "y"}}
    request = MagicMock(side_effect=[Exception("fail"), response])
    monkeypatch.setattr(crud._session, "request", request)

    result = crud.get("c", "d")

    assert result == {"x": "y"}
    assert request.call_count == 2


def test_unavailable_without_auth() -> None:
    assert not FirebaseCRUD(project_id="test-project").available


def test_unavailable_without_backend_url(auth: MagicMock) -> None:
    auth.auth_backend_url = ""
    assert not FirebaseCRUD(auth=auth, project_id="test-project").available


def test_add_returns_none_when_no_auth() -> None:
    crud = FirebaseCRUD(project_id="test-project")
    result = crud.add("c", {"text": "hello"})
    assert result is None
    assert not crud.available
