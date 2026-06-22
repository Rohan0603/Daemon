from __future__ import annotations
import pytest


class TestApplyBrainUpdate:
    def test_apply_brain_update_strips_locked_fields(self):
        from src.brain_schema import BRAIN_SCHEMA, apply_brain_update
        update = {"pet_name": "BAD", "mission_goals": ["goal1"]}
        result = apply_brain_update(update)
        assert "pet_name" not in result
        assert BRAIN_SCHEMA["pet_name"]["locked"] is True

    def test_apply_brain_update_appends_to_list_fields(self):
        from src.brain_schema import apply_brain_update
        update = {"intel_archive": ["item1", "item2"]}
        result = apply_brain_update(update)
        assert "intel_archive" in result
        assert result["intel_archive"] == ["item1", "item2"]

    def test_apply_brain_update_deduplicates_list_items(self):
        from src.brain_schema import apply_brain_update
        update = {"pet_catchphrases": ["a", "b", "a", "c"]}
        result = apply_brain_update(update)
        assert result["pet_catchphrases"] == ["a", "b", "c"]

    def test_apply_brain_update_rejects_unknown_field(self):
        from src.brain_schema import apply_brain_update
        update = {"nonexistent_field": ["data"]}
        result = apply_brain_update(update)
        assert result == {}

    def test_apply_brain_update_rejects_wrong_type(self):
        from src.brain_schema import apply_brain_update
        update = {"pet_catchphrases": "not a list"}
        result = apply_brain_update(update)
        assert result == {}

    def test_apply_brain_update_editable_string_fields_accepted(self):
        from src.brain_schema import apply_brain_update
        update = {"mission_goals": ["goal1"]}
        result = apply_brain_update(update)
        assert "mission_goals" in result

    def test_apply_brain_update_accepts_int(self):
        from src.brain_schema import apply_brain_update
        update = {"pet_affinity_score": 42}
        result = apply_brain_update(update)
        assert result["pet_affinity_score"] == 42

    def test_apply_brain_update_rejects_int_wrong_type(self):
        from src.brain_schema import apply_brain_update
        update = {"pet_affinity_score": "not an int"}
        result = apply_brain_update(update)
        assert result == {}

    def test_apply_brain_update_accepts_map(self):
        from src.brain_schema import apply_brain_update
        update = {"progression_flags": {"keyboard_access_pending": "offered"}}
        result = apply_brain_update(update)
        assert "progression_flags" in result
        assert result["progression_flags"]["keyboard_access_pending"] == "offered"

    def test_apply_brain_update_rejects_map_wrong_type(self):
        from src.brain_schema import apply_brain_update
        update = {"progression_flags": "not a map"}
        result = apply_brain_update(update)
        assert result == {}


class TestBrainSchemaConsistency:
    def test_brain_schema_and_defaults_consistent(self):
        from src.brain_schema import BRAIN_SCHEMA, DEFAULT_BRAIN
        for key in DEFAULT_BRAIN:
            assert key in BRAIN_SCHEMA, f"Key {key!r} in DEFAULT_BRAIN but missing from BRAIN_SCHEMA"
        for key in BRAIN_SCHEMA:
            assert key in DEFAULT_BRAIN, f"Key {key!r} in BRAIN_SCHEMA but missing from DEFAULT_BRAIN"
            t = BRAIN_SCHEMA[key]["type"]
            if t == "list":
                assert isinstance(DEFAULT_BRAIN[key], list), (
                    f"Key {key!r}: BRAIN_SCHEMA type {t!r} but DEFAULT_BRAIN value is {type(DEFAULT_BRAIN[key]).__name__}"
                )
            elif t in ("map", "dict"):
                assert isinstance(DEFAULT_BRAIN[key], dict), (
                    f"Key {key!r}: BRAIN_SCHEMA type {t!r} but DEFAULT_BRAIN value is {type(DEFAULT_BRAIN[key]).__name__}"
                )
            elif t == "int":
                assert isinstance(DEFAULT_BRAIN[key], int), (
                    f"Key {key!r}: BRAIN_SCHEMA type {t!r} but DEFAULT_BRAIN value is {type(DEFAULT_BRAIN[key]).__name__}"
                )
            else:
                assert isinstance(DEFAULT_BRAIN[key], str), (
                    f"Key {key!r}: BRAIN_SCHEMA type {t!r} but DEFAULT_BRAIN value is {type(DEFAULT_BRAIN[key]).__name__}"
                )

    def test_firebase_constants_importable(self):
        from src.constants import FIREBASE_PROJECT_ID
        assert isinstance(FIREBASE_PROJECT_ID, str)


class TestApplyBrainUpdateEdgeCases:
    def test_apply_brain_update_empty_dict(self):
        from src.brain_schema import apply_brain_update
        assert apply_brain_update({}) == {}

    def test_apply_brain_update_mixed_valid_invalid(self):
        from src.brain_schema import apply_brain_update
        update = {
            "pet_name": "locked",
            "pet_catchphrases": "not a list",
            "nonexistent": ["val"],
            "pet_quirks": ["valid one"],
        }
        result = apply_brain_update(update)
        assert "pet_quirks" in result
        assert "pet_name" not in result
        assert "nonexistent" not in result
        assert result["pet_quirks"] == ["valid one"]

    def test_apply_brain_update_multiple_list_fields(self):
        from src.brain_schema import apply_brain_update
        update = {
            "pet_fears": ["fear1", "fear2"],
            "pet_likes": ["like1"],
        }
        result = apply_brain_update(update)
        assert "pet_fears" in result
        assert "pet_likes" in result
        assert result["pet_fears"] == ["fear1", "fear2"]
        assert result["pet_likes"] == ["like1"]

    def test_apply_brain_update_map_merge(self):
        from src.brain_schema import apply_brain_update
        update = {"progression_flags": {"new_flag": "xyz"}}
        result = apply_brain_update(update)
        assert result["progression_flags"] == {"new_flag": "xyz"}
        
    def test_apply_brain_update_new_persona_fields(self):
        from src.brain_schema import apply_brain_update
        update = {
            "user_partner_name": "New Partner",
            "pet_pomodoro_config": {"work_min": 50},
            "screen_time_warn_sec": 7200
        }
        result = apply_brain_update(update)
        assert result["user_partner_name"] == "New Partner"
        assert result["pet_pomodoro_config"] == {"work_min": 50}
        assert result["screen_time_warn_sec"] == 7200

    def test_apply_brain_update_int_value(self):
        from src.brain_schema import apply_brain_update
        result = apply_brain_update({"pet_affinity_score": -10})
        assert result["pet_affinity_score"] == -10


class TestBrainSchemaEdgeCases:
    def test_brain_schema_all_locked_strings_correct(self):
        from src.brain_schema import BRAIN_SCHEMA
        for key, schema in BRAIN_SCHEMA.items():
            if schema["locked"]:
                assert schema["type"] in ("string", "str"), (
                    f"Locked field {key!r} has type {schema['type']!r}, expected 'string' or 'str'"
                )

    def test_default_brain_all_unlocked_lists_have_items(self):
        from src.brain_schema import BRAIN_SCHEMA, DEFAULT_BRAIN
        empties_allowed = {"intel_archive", "user_preferences", "user_long_term_goals", "user_imposed_rules", "intel_insider_knowledge", "user_current_project"}
        for key, schema in BRAIN_SCHEMA.items():
            if not schema["locked"]:
                if schema["type"] == "list":
                    assert isinstance(DEFAULT_BRAIN[key], list)
                    if key not in empties_allowed:
                        assert len(DEFAULT_BRAIN[key]) >= 1, (
                            f"Unlocked list field {key!r} has no items in DEFAULT_BRAIN"
                        )
                elif schema["type"] in ("string", "str"):
                    assert isinstance(DEFAULT_BRAIN[key], str)
                elif schema["type"] == "int":
                    assert isinstance(DEFAULT_BRAIN[key], int)
                elif schema["type"] in ("map", "dict"):
                    assert isinstance(DEFAULT_BRAIN[key], dict)
