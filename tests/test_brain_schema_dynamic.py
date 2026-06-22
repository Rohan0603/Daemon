import json
from pathlib import Path
import pytest


def test_load_schema_from_json_file(tmp_path):
    schema_file = tmp_path / "brain_schema.json"
    schema_data = {
        "version": 1,
        "fields": {
            "test_field": {"type": "str", "locked": False, "default": "hello"}
        }
    }
    schema_file.write_text(json.dumps(schema_data))
    from src.brain_schema import load_brain_schema
    schema = load_brain_schema(schema_path=str(schema_file))
    assert "test_field" in schema
    assert schema["test_field"]["default"] == "hello"


def test_locked_field_preserved(tmp_path):
    schema_file = tmp_path / "brain_schema.json"
    schema_data = {
        "version": 1,
        "fields": {
            "locked_field": {"type": "str", "locked": True, "default": "x"}
        }
    }
    schema_file.write_text(json.dumps(schema_data))
    from src.brain_schema import load_brain_schema
    schema = load_brain_schema(schema_path=str(schema_file))
    assert schema["locked_field"]["locked"] is True


def test_missing_schema_file_raises():
    from src.brain_schema import load_brain_schema
    with pytest.raises(FileNotFoundError):
        load_brain_schema(schema_path="/nonexistent/brain_schema.json")


def test_invalid_field_type_raises(tmp_path):
    schema_file = tmp_path / "brain_schema.json"
    schema_data = {
        "version": 1,
        "fields": {
            "bad_field": {"type": "badtype", "locked": False, "default": ""}
        }
    }
    schema_file.write_text(json.dumps(schema_data))
    from src.brain_schema import load_brain_schema
    with pytest.raises(ValueError, match="Invalid type"):
        load_brain_schema(schema_path=str(schema_file))


def test_apply_brain_update_respects_loaded_schema(tmp_path):
    schema_file = tmp_path / "brain_schema.json"
    schema_data = {
        "version": 1,
        "fields": {
            "custom_field": {"type": "str", "locked": False, "default": ""}
        }
    }
    schema_file.write_text(json.dumps(schema_data))
    from src.brain_schema import load_brain_schema, apply_brain_update
    schema = load_brain_schema(schema_path=str(schema_file))
    updated = apply_brain_update({"custom_field": "hello"}, schema=schema)
    assert updated["custom_field"] == "hello"


def test_apply_brain_update_rejects_locked_field(tmp_path):
    schema_file = tmp_path / "brain_schema.json"
    schema_data = {
        "version": 1,
        "fields": {
            "locked_field": {"type": "str", "locked": True, "default": "orig"}
        }
    }
    schema_file.write_text(json.dumps(schema_data))
    from src.brain_schema import load_brain_schema, apply_brain_update
    schema = load_brain_schema(schema_path=str(schema_file))
    updated = apply_brain_update({"locked_field": "new"}, schema=schema)
    assert "locked_field" not in updated
