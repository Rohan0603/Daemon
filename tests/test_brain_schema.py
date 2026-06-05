from __future__ import annotations
import pytest


class TestApplyBrainUpdate:
    def test_apply_brain_update_strips_locked_fields(self):
        from src.brain_schema import BRAIN_SCHEMA, apply_brain_update
        update = {"daemon_name": "BAD", "long_term_goals": ["goal1"]}
        result = apply_brain_update(update)
        assert "daemon_name" not in result
        assert BRAIN_SCHEMA["daemon_name"]["locked"] is True

    def test_apply_brain_update_appends_to_list_fields(self):
        from src.brain_schema import apply_brain_update
        update = {"blackmail_material": ["item1", "item2"]}
        result = apply_brain_update(update)
        assert "blackmail_material" in result
        assert result["blackmail_material"] == ["item1", "item2"]

    def test_apply_brain_update_deduplicates_list_items(self):
        from src.brain_schema import apply_brain_update
        update = {"daemon_catchphrases": ["a", "b", "a", "c"]}
        result = apply_brain_update(update)
        assert result["daemon_catchphrases"] == ["a", "b", "c"]

    def test_apply_brain_update_rejects_unknown_field(self):
        from src.brain_schema import apply_brain_update
        update = {"nonexistent_field": ["data"]}
        result = apply_brain_update(update)
        assert result == {}

    def test_apply_brain_update_rejects_wrong_type(self):
        from src.brain_schema import apply_brain_update
        update = {"daemon_catchphrases": "not a list"}
        result = apply_brain_update(update)
        assert result == {}

    def test_apply_brain_update_editable_string_fields_accepted(self):
        from src.brain_schema import apply_brain_update
        update = {"long_term_goals": ["goal1"]}
        result = apply_brain_update(update)
        assert "long_term_goals" in result


class TestBrainSchemaConsistency:
    def test_brain_schema_and_defaults_consistent(self):
        from src.brain_schema import BRAIN_SCHEMA, DEFAULT_BRAIN
        for key in DEFAULT_BRAIN:
            assert key in BRAIN_SCHEMA, f"Key {key!r} in DEFAULT_BRAIN but missing from BRAIN_SCHEMA"
        for key in BRAIN_SCHEMA:
            assert key in DEFAULT_BRAIN, f"Key {key!r} in BRAIN_SCHEMA but missing from DEFAULT_BRAIN"
            expected_type = "list" if isinstance(DEFAULT_BRAIN[key], list) else "string"
            actual = BRAIN_SCHEMA[key]["type"]
            assert actual == expected_type, (
                f"Key {key!r}: BRAIN_SCHEMA type {actual!r} doesn't match DEFAULT_BRAIN type {expected_type!r}"
            )

    def test_firebase_constants_importable(self):
        from src.constants import FIREBASE_API_KEY, FIREBASE_PROJECT_ID
        assert isinstance(FIREBASE_API_KEY, str)
        assert isinstance(FIREBASE_PROJECT_ID, str)


class TestApplyBrainUpdateEdgeCases:
    def test_apply_brain_update_empty_dict(self):
        from src.brain_schema import apply_brain_update
        assert apply_brain_update({}) == {}

    def test_apply_brain_update_mixed_valid_invalid(self):
        from src.brain_schema import apply_brain_update
        update = {
            "daemon_name": "locked",
            "daemon_catchphrases": "not a list",
            "nonexistent": ["val"],
            "daemon_quirks": ["valid one"],
        }
        result = apply_brain_update(update)
        assert "daemon_quirks" in result
        assert "daemon_name" not in result
        assert "nonexistent" not in result
        assert result["daemon_quirks"] == ["valid one"]

    def test_apply_brain_update_multiple_list_fields(self):
        from src.brain_schema import apply_brain_update
        update = {
            "daemon_fears": ["fear1", "fear2"],
            "daemon_likes": ["like1"],
        }
        result = apply_brain_update(update)
        assert "daemon_fears" in result
        assert "daemon_likes" in result
        assert result["daemon_fears"] == ["fear1", "fear2"]
        assert result["daemon_likes"] == ["like1"]


class TestBrainSchemaEdgeCases:
    def test_brain_schema_all_locked_strings_correct(self):
        from src.brain_schema import BRAIN_SCHEMA
        for key, schema in BRAIN_SCHEMA.items():
            if schema["locked"]:
                assert schema["type"] == "string", (
                    f"Locked field {key!r} has type {schema['type']!r}, expected 'string'"
                )

    def test_default_brain_all_unlocked_lists_have_items(self):
        from src.brain_schema import BRAIN_SCHEMA, DEFAULT_BRAIN
        empties_allowed = {"recent_blackmail_log", "user_preferences", "insider_knowledge"}
        for key, schema in BRAIN_SCHEMA.items():
            if not schema["locked"]:
                assert schema["type"] == "list"
                assert isinstance(DEFAULT_BRAIN[key], list)
                if key not in empties_allowed:
                    assert len(DEFAULT_BRAIN[key]) >= 1, (
                        f"Unlocked list field {key!r} has no items in DEFAULT_BRAIN"
                    )
