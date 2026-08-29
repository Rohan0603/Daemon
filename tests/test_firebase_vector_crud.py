from unittest.mock import Mock

import pytest

from src.firebase_crud import FirebaseCRUD


def test_find_nearest_vector_uses_native_query():
    crud = FirebaseCRUD(creds_path="unused")
    snapshot = Mock(id="memory-1")
    snapshot.to_dict.return_value = {"text": "python"}
    query = Mock()
    query.stream.return_value = [snapshot]
    collection = Mock()
    collection.find_nearest.return_value = query
    crud._client = Mock()
    crud._available = True
    crud._client.collection.return_value = collection

    results = crud.find_nearest_vector("memories", [1.0, 0.0], limit=2)

    assert results == [{"text": "python", "id": "memory-1"}]
    kwargs = collection.find_nearest.call_args.kwargs
    assert kwargs["vector_field"] == "embedding"
    assert kwargs["limit"] == 2
    assert kwargs["distance_measure"] == "COSINE"


def test_find_nearest_vector_supports_category_prefilter():
    crud = FirebaseCRUD(creds_path="unused")
    crud._client = Mock()
    crud._available = True
    collection = crud._client.collection.return_value
    filtered = collection.where.return_value
    filtered.find_nearest.return_value.stream.return_value = []

    crud.find_nearest_vector(
        "memories", [0.2, 0.8], category_field="type", category_value="diary"
    )

    collection.where.assert_called_once_with("type", "==", "diary")


def test_find_nearest_vector_validates_inputs():
    crud = FirebaseCRUD(creds_path="unused")
    with pytest.raises(ValueError):
        crud.find_nearest_vector("memories", [], limit=5)
    with pytest.raises(ValueError):
        crud.find_nearest_vector("memories", [1], limit=0)
    with pytest.raises(ValueError):
        crud.find_nearest_vector("memories", [1], category_field="type")
    with pytest.raises(ValueError):
        crud.find_nearest_vector("memories", [1], distance_measure="BAD")
