from unittest.mock import MagicMock

import pytest

from src.firebase_crud import FirebaseCRUD


@pytest.fixture
def crud():
    auth = MagicMock()
    auth.get_valid_token.return_value = "test-token"
    return FirebaseCRUD(auth=auth, project_id="test-project")


def test_find_nearest_vector_uses_native_query(crud, monkeypatch):
    response = MagicMock(status_code=200)
    response.json.return_value = [{
        "document": {
            "name": "projects/test-project/databases/(default)/documents/memories/memory-1",
            "fields": {"text": {"stringValue": "python"}},
        }
    }]
    request = MagicMock(return_value=response)
    monkeypatch.setattr(crud._session, "request", request)
    results = crud.find_nearest_vector("memories", [1.0, 0.0], limit=2)

    assert results == [{"text": "python", "id": "memory-1"}]
    query = request.call_args.kwargs["json"]["structuredQuery"]
    assert query["findNearest"]["vectorField"] == {"fieldPath": "embedding"}
    assert query["findNearest"]["limit"] == 2
    assert query["findNearest"]["distanceMeasure"] == "COSINE"
    assert query["findNearest"]["queryVector"]["mapValue"]["fields"]["value"] == {
        "arrayValue": {"values": [{"doubleValue": 1.0}, {"doubleValue": 0.0}]}
    }


def test_find_nearest_vector_supports_category_prefilter(crud, monkeypatch):
    response = MagicMock(status_code=200)
    response.json.return_value = []
    request = MagicMock(return_value=response)
    monkeypatch.setattr(crud._session, "request", request)

    crud.find_nearest_vector(
        "memories", [0.2, 0.8], category_field="type", category_value="diary"
    )

    query = request.call_args.kwargs["json"]["structuredQuery"]
    assert query["where"] == {
        "fieldFilter": {
            "field": {"fieldPath": "type"},
            "op": "EQUAL",
            "value": {"stringValue": "diary"},
        }
    }


def test_find_nearest_vector_validates_inputs(crud):
    with pytest.raises(ValueError):
        crud.find_nearest_vector("memories", [], limit=5)
    with pytest.raises(ValueError):
        crud.find_nearest_vector("memories", [1], limit=0)
    with pytest.raises(ValueError):
        crud.find_nearest_vector("memories", [1], category_field="type")
    with pytest.raises(ValueError):
        crud.find_nearest_vector("memories", [1], distance_measure="BAD")
