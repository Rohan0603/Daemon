from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from src.firebase_crud import FirebaseCRUD


@pytest.fixture
def mock_firestore():
    with patch("src.firebase_crud.firestore.client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_credentials():
    with patch("src.firebase_crud.credentials.Certificate") as mock_cert:
        yield mock_cert


@pytest.fixture
def mock_firebase_admin():
    with patch("src.firebase_crud.firebase_admin") as mock_admin:
        yield mock_admin


@pytest.fixture
def crud(mock_credentials, mock_firebase_admin, mock_firestore) -> FirebaseCRUD:
    # Set a small retry delay for tests so they don't block
    FirebaseCRUD._RETRY_BASE_DELAY = 0.01
    return FirebaseCRUD(creds_path="dummy/path")


# ── get ─────────────────────────────────────────────────────────────────────

def test_get_document_exists(crud: FirebaseCRUD, mock_firestore) -> None:
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"key": "val"}

    mock_client_instance = mock_firestore.return_value
    mock_client_instance.collection.return_value.document.return_value.get.return_value = mock_doc

    result = crud.get("c", "d")
    assert result == {"key": "val"}
    mock_client_instance.collection.assert_called_with("c")
    mock_client_instance.collection().document.assert_called_with("d")


def test_get_document_not_found(crud: FirebaseCRUD, mock_firestore) -> None:
    mock_doc = MagicMock()
    mock_doc.exists = False

    mock_client_instance = mock_firestore.return_value
    mock_client_instance.collection.return_value.document.return_value.get.return_value = mock_doc

    result = crud.get("c", "missing")
    assert result is None


def test_get_network_error_returns_none(crud: FirebaseCRUD, mock_firestore) -> None:
    mock_client_instance = mock_firestore.return_value
    mock_client_instance.collection.return_value.document.return_value.get.side_effect = Exception("timeout")

    result = crud.get("c", "d")
    assert result is None
    # In the firebase-admin implementation, a network error during retry doesn't set available to False.
    assert crud.available


# ── set ─────────────────────────────────────────────────────────────────────

def test_set_no_merge(crud: FirebaseCRUD, mock_firestore) -> None:
    mock_client_instance = mock_firestore.return_value
    ok = crud.set("c", "d", {"key": "val"}, merge=False)
    assert ok is True
    mock_client_instance.collection.return_value.document.return_value.set.assert_called_once_with({"key": "val"}, merge=False)


def test_set_with_merge_preserves_existing(crud: FirebaseCRUD, mock_firestore) -> None:
    mock_client_instance = mock_firestore.return_value
    ok = crud.set("c", "d", {"key": "new"}, merge=True)
    assert ok is True
    mock_client_instance.collection.return_value.document.return_value.set.assert_called_once_with({"key": "new"}, merge=True)


# ── add ─────────────────────────────────────────────────────────────────────

def test_add_document(crud: FirebaseCRUD, mock_firestore) -> None:
    mock_client_instance = mock_firestore.return_value
    mock_result = MagicMock()
    mock_result.id = "auto123"
    mock_client_instance.collection.return_value.add.return_value = (None, mock_result)

    doc_id = crud.add("c", {"text": "hello"})
    assert doc_id == "auto123"
    mock_client_instance.collection.return_value.add.assert_called_once_with({"text": "hello"})


# ── delete ──────────────────────────────────────────────────────────────────

def test_delete_document(crud: FirebaseCRUD, mock_firestore) -> None:
    mock_client_instance = mock_firestore.return_value
    ok = crud.delete("c", "d")
    assert ok is True
    mock_client_instance.collection.return_value.document.return_value.delete.assert_called_once()


# ── query ───────────────────────────────────────────────────────────────────

def test_query_collection(crud: FirebaseCRUD, mock_firestore) -> None:
    mock_doc1 = MagicMock()
    mock_doc1.to_dict.return_value = {"x": "a"}
    mock_doc2 = MagicMock()
    mock_doc2.to_dict.return_value = {"x": "b"}

    mock_client_instance = mock_firestore.return_value
    mock_client_instance.collection.return_value.stream.return_value = [mock_doc1, mock_doc2]

    docs = crud.query("c")
    assert len(docs) == 2
    assert docs[0]["x"] == "a"
    assert docs[1]["x"] == "b"


def test_query_empty_collection(crud: FirebaseCRUD, mock_firestore) -> None:
    mock_client_instance = mock_firestore.return_value
    mock_client_instance.collection.return_value.stream.return_value = []

    docs = crud.query("c")
    assert docs == []


# ── read_all_text ───────────────────────────────────────────────────────────

def test_read_all_text(crud: FirebaseCRUD, mock_firestore) -> None:
    mock_doc1 = MagicMock()
    mock_doc1.to_dict.return_value = {"text": "hello"}
    mock_doc2 = MagicMock()
    mock_doc2.to_dict.return_value = {"text": "world"}

    mock_client_instance = mock_firestore.return_value
    mock_client_instance.collection.return_value.stream.return_value = [mock_doc1, mock_doc2]

    texts = crud.read_all_text("c")
    assert texts == ["hello", "world"]


# ── retry ───────────────────────────────────────────────────────────────────

def test_retry_succeeds_on_second_attempt(crud: FirebaseCRUD, mock_firestore) -> None:
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"x": "y"}

    # First call fails, second succeeds
    mock_get = MagicMock(side_effect=[Exception("fail"), mock_doc])

    mock_client_instance = mock_firestore.return_value
    mock_client_instance.collection.return_value.document.return_value.get = mock_get

    result = crud.get("c", "d")
    assert result == {"x": "y"}
    assert mock_get.call_count == 2


# ── unavailable recovery ────────────────────────────────────────────────────

def test_available_resets_on_new_crud() -> None:
    c = FirebaseCRUD(creds_path="dummy/path")
    assert c.available


def test_add_returns_none_when_no_auth(crud: FirebaseCRUD) -> None:
    crud._available = False
    result = crud.add("c", {"text": "hello"})
    assert result is None
    assert not crud.available
